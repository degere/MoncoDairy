# Crea los roles y los usuarios de la demo en el backend Django (usa el registro del
# primer usuario: solo funciona sin token mientras la tabla de usuarios esta vacia).
#   .\scripts\crear_usuarios_demo.ps1 -AdminEmail admin@ejemplo.cl -AdminPin 000000 `
#       -WorkerEmail trabajador@ejemplo.cl -WorkerPin 000000
param(
    [string]$Base = 'http://localhost:8000',
    [Parameter(Mandatory)][string]$AdminEmail,
    [Parameter(Mandatory)][string]$AdminPin,
    [Parameter(Mandatory)][string]$WorkerEmail,
    [Parameter(Mandatory)][string]$WorkerPin
)

function Detalle($e) {
    if ($e.ErrorDetails -and $e.ErrorDetails.Message) { return $e.ErrorDetails.Message }
    return $e.Exception.Message
}

# PowerShell 5 puede devolver la lista de roles como arreglo anidado: se aplana.
function Aplanar($x) {
    foreach ($i in $x) { if ($i -is [array]) { Aplanar $i } else { $i } }
}

function RolId($roles, $nombre) {
    $r = @(Aplanar $roles) | Where-Object { $_.nombre -eq $nombre } | Select-Object -First 1
    if ($r) { return [int]$r.id }
    return $null
}

function Llamar($Metodo, $Ruta, $Cuerpo = $null, $Token = $null) {
    $h = @{}
    if ($Token) { $h['Authorization'] = "Bearer $Token" }
    $p = @{ Method = $Metodo; Uri = "$Base$Ruta"; Headers = $h; ContentType = 'application/json' }
    if ($Cuerpo) { $p['Body'] = ($Cuerpo | ConvertTo-Json) }
    Invoke-RestMethod @p
}

# 1) Primer usuario (administrador): crea los roles y se registra sin token.
try {
    $roles = Llamar 'GET' '/api/auth/roles/'
    foreach ($n in 'ADMINISTRADOR', 'LECHERO') {
        if (-not (RolId $roles $n)) { [void](Llamar 'POST' '/api/auth/roles/' @{ nombre = $n }) }
    }
    $roles = Llamar 'GET' '/api/auth/roles/'
    $rolAdmin = RolId $roles 'ADMINISTRADOR'
    [void](Llamar 'POST' '/api/auth/registro-pin/' @{ nombre = 'Administrador Demo'; email = $AdminEmail; rol = $rolAdmin; pin = $AdminPin; activo = $true })
    Write-Host "Administrador creado: $AdminEmail"
} catch {
    Write-Host "No se pudo crear el administrador sin token: $(Detalle $_)"
    Write-Host "(Si ya hay usuarios en la base es normal; se sigue con el login.)"
}

# 2) Login del administrador y alta del trabajador.
try {
    $login = Llamar 'POST' '/api/auth/login-pin/' @{ email = $AdminEmail; pin = $AdminPin }
} catch {
    Write-Host "No se pudo entrar como administrador: $(Detalle $_)"
    exit 1
}
$token = $login.tokens.access
$roles = Llamar 'GET' '/api/auth/roles/' $null $token
$rolLechero = RolId $roles 'LECHERO'
try {
    [void](Llamar 'POST' '/api/auth/registro-pin/' @{ nombre = 'Trabajador Demo'; email = $WorkerEmail; rol = $rolLechero; pin = $WorkerPin; activo = $true } $token)
    Write-Host "Trabajador creado: $WorkerEmail"
} catch {
    Write-Host "El trabajador ya existe o no se pudo crear: $(Detalle $_)"
}
Write-Host "Listo. Entra a la app con $WorkerEmail y su PIN."
