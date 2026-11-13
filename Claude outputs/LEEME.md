# Conexion de MoncoDairy a Firebase Realtime Database

## Como aplicar
1. Descomprime este zip DENTRO de la carpeta del proyecto Flutter (la que tiene pubspec.yaml).
   Se agregan: `lib/data/`, `lib/widgets/panel_sensores.dart`, `lib/firebase_bootstrap.dart`, `instalar.ps1`.
   No pisa archivos tuyos.
2. En esa carpeta ejecuta: `powershell -ExecutionPolicy Bypass -File .\instalar.ps1`
   (instala dependencias y genera `lib/firebase_options.dart` + `google-services.json`).
   Como el proyecto de Firebase ya existe, en flutterfire elige `appmoncopullisensores`.
3. Edita `lib/main.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'firebase_bootstrap.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final repo = await inicializarFirebase();
  runApp(
    Provider.value(
      value: repo,
      child: const MiApp(), // <- tu app actual
    ),
  );
}
```

4. Donde hoy usas el "corral de testeo", pon:

```dart
PanelSensores(
  // Opcional: tu propio diseno con los datos reales
  contenidoBuilder: (context, r) => TuWidget(
    temperatura: r.temperaturaC,
    humedad: r.humedadPct,
    dispositivo: r.dispositivo,
  ),
)
```
   Debe estar dentro de un widget con altura acotada (por ejemplo el body de un Scaffold o un Expanded).
   Si no pasas `contenidoBuilder`, muestra tarjetas por defecto.

## Android
- `android/app/src/main/AndroidManifest.xml` debe tener
  `<uses-permission android:name="android.permission.INTERNET"/>` (en release).
- El `applicationId` en `android/app/build.gradle(.kts)` debe ser `cl.apisensores`.
- `minSdk` 23 o superior.

## Reglas de Firebase
Si la lectura da `permission-denied`, revisa las reglas de la base. Minimo recomendado:
`{ "rules": { "telemetria": { ".read": "auth != null", ".write": false } } }`
(esto exigiria autenticar a la app; si aun no usas Auth, deja la lectura abierta solo mientras pruebas).

## Comportamiento
- Muestra el registro mas reciente de `/telemetria` (claves push, orden cronologico).
- Valida temperatura -20..70 y humedad 0..100; si no es valido muestra "Sin lecturas validas".
- Estados: cargando, error, sin datos, datos y banner de "sin conexion".
