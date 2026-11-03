# MoncoDairy Sense (Flutter)

## Cómo ejecutarlo
```bash
flutter create moncodairy_sense --platforms android --org cl.moncodairy
# copia lib/ y pubspec.yaml de este zip encima del proyecto creado
cd moncodairy_sense
flutter pub get
flutter run
```
Login de prueba: cualquier usuario + PIN de 6 dígitos.

## Estructura
- `lib/models`      → Corral, Sensor, Aviso
- `lib/data`        → `Repository` (contrato) + `MockRepository` (datos falsos)
- `lib/screens`     → Login, Corrales, Detalle corral, Detalle sensor, Avisos, Sensores, Historial
- `lib/widgets`     → componentes reutilizables
- `lib/core`        → tema y colores

## Plan de conexión
1. `ApiRepository` (Dio → Django REST): login, corrales, avisos, historial + caché offline (drift/sqflite).
2. `FirebaseRepository`: lecturas en vivo de los sensores (Realtime Database) → reemplaza humedad/temperatura actuales.
3. En `main.dart`: `Repository.instance = ApiRepository(...)`. La UI no cambia.
