# Diseño: flujo sensor → Firebase → Django → app (punto 4 de la Evaluación 3)

Fecha: 2026-11-16 · Estado: **borrador para aprobación** (no se ha construido nada)
Proyecto: MoncoDairy Sense, equipo AgroSalud Tech, caso Agrícola Moncopulli S.A.

## 1. Intención y por qué

Hoy la app es una maqueta: el login acepta cualquier usuario con PIN de 6 dígitos, casi todos los datos son simulados y solo el Corral 1 muestra lecturas reales, leídas directo de Firebase. Además, el sensor físico y la app no usan la misma base (ver §2), y Django, donde viven el motor de alertas y los usuarios, nunca recibe las lecturas reales.

El equipo quiere un flujo único y estable, y poder demostrarlo en la defensa:

```
Sensor DHT22 (WeMos D1)
   │  cada 30 s
   ▼
Firebase Realtime Database  (proyecto cuidado-de-vacas)
   │  puente (script Python), consulta cada 10 s
   ▼
Django API (/api/iot/ingesta/ → guarda lectura y genera alertas)
   ▲  la app consulta cada 30 s (Bearer del login)
   │
App Flutter (emulador y celular real)
```

Criterio de éxito: una lectura real del DHT22 aparece en la app, marcada "EN VIVO", en menos de ~40 s en el caso normal; una lectura fuera de umbral genera una alerta en Django y se ve en la app; el mismo flujo se muestra en un emulador y en un celular real.

## 2. Estado actual (verificado en los archivos el 2026-11-16)

- Sketch `Documents\Arduino\CuidadodeTerneros\CuidadodeTerneros.ino` (última modificación 10-11-2026): escribe con `pushJSON` en `/telemetria` del proyecto `appmoncopullisensores`, nodo `WEMOS-D1-01`, en modo prueba (`test_mode`, sin login), cada 10 s (lee cada 3 s). Si el DHT22 falla envía 0,0 con `estado_filtrado = "ERROR_SENSOR"` (el comentario del sketch dice que es para pasar las reglas de validación de Firebase). Existe una copia distinta en `Downloads\CuidadodeTerneros\` con la misma URL y ruta.
- App (`Flutter/lib/data/firebase_repository.dart`, con cambios sin commit): lee `cuidado-de-vacas`, ruta `buffer_sensores_terreno/NODE-PARTOS-02`, con sesión anónima. Reutiliza `MockRepository` para login, avisos, sensores e historial. El Corral 1 es el único con datos reales (`kCorralConSensorReal = 1`). `Repository` es una interfaz con `login`, `getCorrales`, `getSensores`, `getAvisos`, `getHumedad24h`, `watchCorrales`, `watchCorral`; su comentario ya prevé un `ApiRepository`.
- `pubspec.yaml` no tiene paquete HTTP. `AndroidManifest.xml` solo declara `INTERNET` (el tráfico HTTP sin cifrar está bloqueado por defecto en Android 9 o superior).
- Django en la rama evaluada (`Flutter`, con 18 archivos modificados sin commit): solo tiene `/api/iot/ingesta/`, `/api/ordena/rfid/`, `/api/auth/login-pin/` y `/api/auth/registro-pin/`, todos sin autenticación. No existe ningún endpoint de lectura para la app. `Sensor` tiene solo `ubicacion`, `tipo`, `estado`: no hay corral ni identificador de nodo.
- Rama `Pin-de-Acceso` (no integrada): token Bearer firmado (TTL 8 h, `login-pin` lo entrega), clave `X-API-Key` para nodos IoT (`IOT_API_KEY` en `.env`), permisos `EsTrabajadorONodoIoT` y `EsAdministradorAutenticado`, límite de intentos en el login, `.env.example` y migración `0001_initial.py`. Toca los mismos archivos de Django que tienen cambios sin commit en `Flutter`.
  - Su ingesta es una versión más completa de la del árbol de trabajo (verificado comparando ambas): mismos umbrales (frío < 10 °C, calor > 25 °C, humedad ≥ 80 %), pero además rechaza valores NaN o infinitos, exige que el sensor tenga `estado = "ACTIVO"`, valida el rango según `Sensor.tipo` (el tipo debe contener `TEMP` o `HUM`) y acepta solo las unidades `C`, `°C`, `CELSIUS`, `%`, `HR`, `%HR`. Guarda lectura y alerta en una transacción y **no repite alertas**: no crea una alerta nueva del mismo tipo y sensor mientras haya una con `estado_lectura = "PENDIENTE"` creada en los últimos 60 minutos (`ALERTA_COOLDOWN_MINUTOS`).
  - Su carpeta `Flutter/` es otra: tiene `local_database.dart` y otro `main.dart`, y no tiene `firebase_repository.dart` ni `telemetria_registro.dart`. El trabajo de la app con Firebase vive solo en la rama `Flutter`.
- `django/db.sqlite3` del árbol de trabajo está vacío (0 usuarios, 0 roles, 0 sensores): la demo necesita una siembra de datos.

## 3. Objetivos, no objetivos y antiobjetivos

**Objetivos**
1. Sensor y puente usan un solo proyecto de Firebase: `cuidado-de-vacas`.
2. Un puente copia cada lectura válida de Firebase a Django mediante `POST /api/iot/ingesta/`, de modo que el motor de alertas existente corre sobre datos reales.
3. La app consulta solo a Django: login real con PIN y lecturas del Corral 1 con refresco cada 30 s, más las alertas.
4. Funciona con Django en un PC, y la app en un emulador y en un celular real en la misma red.

**No objetivos** (fuera de alcance, decididos o confirmados)
- Bloqueo de leche por tratamiento: el cliente ya lo tiene; no se implementa.
- Los demás corrales (siguen simulados), historial de humedad 24 h, lista de sensores, caché offline, almacenamiento seguro del token, despliegue público de Django, migrar a PostgreSQL.
- Cambiar las reglas del motor de alertas o hacer que no repita alertas.
- Borrar `FirebaseRepository` o los paquetes de Firebase de la app: se deja de usar, no se elimina.

**Antiobjetivos** (fallaría aunque "funcione")
- Que funcione solo con el simulador y no con el DHT22 real.
- Dejar la API abierta, o subir al repositorio claves, la contraseña del Wi-Fi o la cuenta de servicio de Firebase.
- Alertas falsas: una lectura de error (0,0) jamás debe llegar a Django como medición real.
- Que la demo dependa de una red que bloquea la comunicación entre celular y PC.

## 4. Enfoques considerados

- **A. Sensor directo a Django, app solo con Django.** Un solo almacén, pero hay que reescribir más de la app, se pierde el tiempo real de Firebase y la placa necesita alcanzar el servidor Django por Wi-Fi. Descartado.
- **B. Sensor → Firebase → puente → Django → app. Elegido por el equipo.** Aprovecha el sensor y Firebase que ya funcionan, mantiene la interfaz `Repository` y reutiliza el motor de alertas. Costo: una pieza más en ejecución (el puente).
- **C. Solo unificar sensor y app en Firebase.** Rápido, pero sin alertas reales de Django. Descartado.

Variante elegida dentro de B (por el equipo): la app **no** lee Firebase; lee solo Django, para que todo pase por el mismo punto.

## 5. Diseño

### 5.1 Sketch del sensor (archivo nuevo, no se modifica el original)
- Archivo nuevo `CuidadodeTerneros_v2.ino` en `iot/` del repositorio. Las copias existentes no se tocan.
- `DATABASE_URL` → `https://cuidado-de-vacas-default-rtdb.firebaseio.com`. Ruta de escritura `/buffer_sensores_terreno/WEMOS-D1-01` con `pushJSON` (la convención `buffer_sensores_terreno/<node_id>/<push_id>` ya está documentada en `firebase_repository.dart`). Se mantiene la estructura actual del registro (`dispositivo`, `lecturas_crudas`, `filtro_y_validacion`, `marcas_tiempo`).
- Envío cada **30 s** (hoy 10 s).
- Credenciales (Wi-Fi, API key de Firebase) en un `secrets.h` ignorado por git, con un `secrets.h.example` sin valores.
- Autenticación: registro anónimo (`Firebase.signUp` con correo y contraseña vacíos) en lugar de `test_mode`, porque las reglas de la base exigen autenticación (según lo anotado en el proyecto; el constructor debe confirmarlo en la consola). Si el registro anónimo no está habilitado, se usa un usuario de correo y contraseña dedicado.
- Si el DHT22 falla se sigue enviando el registro con `estado_filtrado = "ERROR_SENSOR"` y 0,0. El comentario del sketch dice que las reglas de validación lo exigen, pero eso se escribió para el proyecto `appmoncopullisensores`: **las reglas de `cuidado-de-vacas` no se han visto**. Decisión mía: mantener el comportamiento para poder mostrar el fallo; el puente descarta esos registros.
- **Primera tarea de construcción (puerta de verificación):** obtener las reglas de `cuidado-de-vacas` (consola de Firebase, Realtime Database, Reglas) y comprobar que aceptan escrituras autenticadas en `buffer_sensores_terreno/WEMOS-D1-01` con esta estructura de registro y con el registro de error. Si no la aceptan, se ajusta el sketch o las reglas antes de seguir. El nodo `NODE-PARTOS-02` que lee hoy la app lo publica el simulador (según el comentario de `firebase_repository.dart`) y no forma parte del flujo nuevo.

### 5.2 Puente Firebase → Django (`puente/puente_firebase.py`, carpeta nueva)
- Script independiente de Python, con su propio `requirements.txt` (`firebase-admin`, `requests`). Se ejecuta en el mismo PC que Django, junto a `runserver`.
- Lee Firebase con una cuenta de servicio (Admin SDK, no depende de las reglas). La ruta al archivo JSON y el resto de la configuración vienen de variables de entorno (`FIREBASE_CREDENTIALS`, `FIREBASE_DB_URL`, `DJANGO_URL`, `IOT_API_KEY`). El JSON nunca se guarda en el repositorio.
- Cada **10 s** consulta, para cada nodo del archivo de configuración, los registros nuevos ordenados por clave (las claves de `pushJSON` son cronológicas) y guarda la última clave procesada en `puente/estado_puente.json`. En la primera ejecución arranca desde el último registro, sin recuperar el historial (decisión mía, para no inundar Django).
- Por cada registro con `estado_filtrado == "VALIDO"` reenvía los valores de `lecturas_crudas` (no hay otro valor filtrado) con dos `POST /api/iot/ingesta/` y encabezado `X-API-Key`: temperatura (`unidad` `°C`) y humedad (`unidad` `%`), con el `sensor_id` de cada uno según `puente/nodos.json`. El sketch solo escribe dos estados (`VALIDO` y `ERROR_SENSOR`) y no clasifica umbrales: una lectura fuera de umbral sigue siendo `VALIDO` y es Django quien genera la alerta. Los registros `ERROR_SENSOR` se descartan y se anotan en el log.
- `puente/nodos.json`: `{"WEMOS-D1-01": {"corral_id": 1, "sensor_temperatura": <id>, "sensor_humedad": <id>}}`. No cambia el esquema de la base. Un script de siembra crea las dos filas de `Sensor` con `ubicacion = "Corral 1"`, `tipo` `TEMPERATURA` / `HUMEDAD` y `estado = "ACTIVO"` (la ingesta rechaza sensores no activos), y no duplica si ya existen.
- Si Django no responde, el puente no avanza la última clave y reintenta en el siguiente ciclo. Un registro que Django rechaza con 400 (fuera de rango físico) se registra y se salta.
- Limitación aceptada: Django guarda `fecha_hora` con su hora de llegada (el ingreso usa `timezone.now()`), no con la hora de la medición.

### 5.3 Django (sobre la rama `Pin-de-Acceso`)
- Base: la autenticación y los permisos de `Pin-de-Acceso` (ver §6).
- Endpoint nuevo `GET /api/corrales/<corral_id>/estado/` (solo Bearer de trabajador autenticado): devuelve la última lectura de temperatura y de humedad de los sensores con `ubicacion = "Corral <id>"` (`valor`, `unidad`, `fecha_hora`), la antigüedad en segundos y `en_vivo` (verdadero si la última lectura tiene ≤ 90 s, es decir 3 intervalos del sensor).
- Endpoint nuevo `GET /api/alertas/?corral=<id>&limite=20` (solo Bearer): últimas alertas, de la más reciente a la más antigua.
- Se agrega un permiso mínimo que acepte solo token Bearer (sin `X-API-Key`), para que la clave del nodo IoT no sirva para leer datos.
- El contrato de `/api/iot/ingesta/` no cambia. Se escriben pruebas nuevas en un archivo aparte.
- Siembra de la demo (la base está vacía): un script (comando de gestión o script para `manage.py shell`, a criterio del constructor) crea los roles `ADMINISTRADOR` y `LECHERO`, un administrador y un trabajador con PIN, y los dos sensores. Los PIN y correos de la demo los define el equipo y se pasan por variables de entorno al sembrar; no se escriben en el repositorio. El login de la app usa el trabajador; el administrador solo se necesita para crear más usuarios con `registro-pin`, que exige rol `ADMINISTRADOR`.
- Convención temporal: el corral se identifica por el texto de `Sensor.ubicacion` ("Corral 1"). Es frágil, pero evita una migración; queda como deuda documentada.

### 5.4 App Flutter
- Nueva clase `ApiRepository implements Repository`, que `main.dart` asigna en lugar de `FirebaseRepository`.
- `login` llama a `POST /api/auth/login-pin/` y guarda el token Bearer en memoria; si falla muestra el error de la API (credenciales inválidas, bloqueo por intentos).
- `watchCorrales` / `watchCorral`: para el Corral 1 consultan `/estado/` con un `Timer.periodic` de 30 s (y una consulta inmediata al abrir); marcan `enVivo` según el campo de Django. Los demás corrales siguen con `MockRepository`.
- `getAvisos` muestra las alertas del Corral 1 junto a los avisos simulados.
- Paquete nuevo `http` en `pubspec.yaml`.
- URL base por `--dart-define=API_BASE_URL=...`: emulador `http://10.0.2.2:8000`; celular real `http://<IP del PC>:8000`.
- Tráfico HTTP: `android:usesCleartextTraffic="true"` solo en el manifiesto de depuración (`android/app/src/debug/AndroidManifest.xml`), para no afectar una compilación de producción.

### 5.5 Red y entorno de la demo
- Django: `runserver 0.0.0.0:8000`; `ALLOWED_HOSTS` en `.env` con la IP del PC; regla de entrada en el Firewall de Windows para TCP 8000 en red privada.
- Celular y PC en la misma Wi-Fi. Riesgo: muchas redes institucionales aíslan los dispositivos entre sí. Plan B: punto de acceso del PC o del celular, o conectar el celular por USB y usar `adb reverse tcp:8000 tcp:8000` con `API_BASE_URL=http://localhost:8000`.
- El sensor solo necesita internet para llegar a Firebase.

### 5.6 Latencia y frecuencia
Sensor 30 s, puente 10 s, app 30 s. Caso normal desde que el sensor envía hasta que la app lo muestra: hasta ~40 s. "Cada 30 s" describe cuándo se actualiza la app, no la latencia total.

## 6. Restricciones
- No se modifica el código de producción hasta que este diseño se apruebe.
- Los datos de `db.sqlite3` no se publican; las claves y credenciales no se reproducen en documentos ni logs.
- Hay 18 archivos modificados sin commit en la rama `Flutter`, y `Pin-de-Acceso` cambia los mismos archivos de Django y tiene una carpeta `Flutter/` distinta (§2). **Llamada mía (el equipo la confirma al aprobar):** trabajar en un `git worktree` separado, con una rama nueva creada desde `Flutter` para la app, y traer a ella la carpeta `django/` de `Pin-de-Acceso` (`git checkout Pin-de-Acceso -- django`). Así el árbol de trabajo actual, con la versión evaluada de la Evaluación 3, no se toca y no se pierde nada. Los cambios sin commit de la app que la compilación necesite (configuración de Gradle, `firebase_options`) se copian de ese árbol al nuevo; el constructor debe verificar que la app compila allí con `flutter pub get` y `flutter analyze`. Las ediciones sin commit de `django/` en `Flutter` no se portan: `Pin-de-Acceso` contiene una versión más completa de la ingesta y del motor de alertas.
- Alertas: con el cooldown de `Pin-de-Acceso` hay como máximo una alerta pendiente por tipo y sensor cada 60 minutos. Para repetir la demostración de una alerta hace falta un script de reinicio de la demo (borra o cierra las alertas pendientes de los sensores de demostración); no se cambia el valor de `ALERTA_COOLDOWN_MINUTOS`. La app muestra las 20 alertas más recientes.

## 7. Verificación
- Pruebas de Django para los dos endpoints nuevos (con y sin token, token expirado, corral sin sensores, lectura vieja → `en_vivo` falso).
- El puente se escribe con una función pura `procesar_registro(registro, config)` para probarla sin Firebase (VALIDO, ERROR_SENSOR, campos faltantes, valores fuera de rango, duplicado).
- Prueba de punta a punta manual: crear un registro de prueba en Firebase → comprobar `LecturaSensor` y `Alerta` en Django → comprobar el endpoint → verlo en el emulador y en el celular; repetir con el DHT22 real y con un valor forzado fuera de umbral.
- Se vuelve a ejecutar la batería existente de la Evaluación 3 para comprobar que no hay regresiones y se actualiza el informe (discrepancias D relacionadas con el punto 4 y la recomendación asociada).

## 8. Lo que queda al constructor
Estructura interna de los módulos, nombres de variables, formato del log del puente, diseño visual del indicador "sin datos recientes" en la app y el detalle de las pruebas.
