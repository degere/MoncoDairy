# Corre todas las pruebas del proyecto. Ejecutar desde la raiz del repo:
#   .\scripts\correr_tests.ps1
# Requiere: venv de Python con `pip install -r django\requirements.txt` y Flutter en el PATH.
param(
    [switch]$SoloDjango,
    [switch]$SoloFlutter
)

$ErrorActionPreference = 'Continue'
$raiz = Split-Path -Parent $PSScriptRoot
$fallos = @()

function Paso($nombre, $dir, [scriptblock]$cmd) {
    Write-Host "`n=== $nombre ===" -ForegroundColor Cyan
    Push-Location $dir
    try {
        & $cmd
        if ($LASTEXITCODE -ne 0) { $script:fallos += $nombre; Write-Host "FALLO: $nombre" -ForegroundColor Red }
        else { Write-Host "OK: $nombre" -ForegroundColor Green }
    } finally { Pop-Location }
}

if (-not $SoloFlutter) {
    Paso 'Django: migraciones al dia' "$raiz\django" { python manage.py makemigrations --check --dry-run }
    Paso 'Django: manage.py check'    "$raiz\django" { python manage.py check }
    Paso 'Django: tests (sensores)'   "$raiz\django" { python manage.py test sensores -v 2 }
}

if (-not $SoloDjango) {
    Paso 'Flutter: pub get' "$raiz\Flutter" { flutter pub get }
    Paso 'Flutter: analyze' "$raiz\Flutter" { flutter analyze }
    Paso 'Flutter: test'    "$raiz\Flutter" { flutter test }
}

Write-Host ''
if ($fallos.Count -eq 0) { Write-Host 'TODO OK' -ForegroundColor Green; exit 0 }
Write-Host ('Fallaron: ' + ($fallos -join ', ')) -ForegroundColor Red
exit 1
