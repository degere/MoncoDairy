# Ejecutar desde la raiz del proyecto Flutter (donde esta pubspec.yaml):
#   powershell -ExecutionPolicy Bypass -File .\instalar.ps1
$ErrorActionPreference = "Stop"

flutter pub add firebase_core firebase_database provider

# Requiere Firebase CLI con sesion iniciada (firebase login) y flutterfire_cli
dart pub global activate flutterfire_cli
flutterfire configure --android-package-name=cl.apisensores

Write-Host ""
Write-Host "Listo. Ahora aplica los 2 cambios manuales de LEEME.md (main.dart y el reemplazo del corral de testeo)."
