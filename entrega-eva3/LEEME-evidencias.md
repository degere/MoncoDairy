# Evidencias Eva-3 — AgroSalud Tech (MoncoDairy Sense)

Fecha de ejecución: 16-11-2026 · Equipo: Windows + PowerShell · Python 3.14.6 · Flutter 3.47.9 (Dart 3.13.7)

Todo se ejecutó sobre una **copia** del proyecto (carpeta temporal), con un entorno virtual nuevo y una base
SQLite vacía. En el repositorio solo se agregó esta carpeta `entrega-eva3/`; no se modificó ningún archivo existente.

## Contenido

| Ruta | Qué es |
|---|---|
| `Informe_Final_Eva3_AgroSalud_Tech.docx` | Informe final |
| `pruebas/django/tests_eva3.py` | 48 casos P0xx (Django) |
| `pruebas/django/smoke_api_live.py` | 19 casos L01–L19 contra la API levantada |
| `pruebas/django/seed_eva3.py` | Datos semilla para la prueba en vivo |
| `pruebas/django/consultas_orm.py` | Índices (PRAGMA) y conteo de consultas SQL |
| `pruebas/flutter/eva3_test.dart` | 18 casos F-0xx (Flutter) |
| `pruebas/flutter/capturas_test.dart` | Genera las 8 capturas PNG |
| `evidencias/logs/*.txt` | Salidas completas de cada ejecución |
| `evidencias/capturas/*.png` | Capturas de pantalla |

## Versión evaluada

```
git branch            -> * Flutter
git log -1 --oneline  -> beab1e1 Eliminacion de basura (13-11-2026)
git status --short    -> 18 archivos modificados (M) y 9 rutas sin seguimiento (??),
                         entre ellas django/sensores/migrations/0001_initial.py
```

## 1. Backend Django (versión evaluada)

```powershell
cd <copia>\django
python -m venv .venv ; .venv\Scripts\Activate.ps1
pip install -r requirements.txt        # Django 6.1.2, DRF 3.18.3, django-environ 0.14.0
python manage.py check                 # System check identified no issues (0 silenced).
python manage.py check --deploy        # 1 error (mail.E001) + 6 warnings (W004, W008, W009, W012, W016, W018)
python manage.py makemigrations --check --dry-run   # No changes detected
python manage.py migrate               # 19 migraciones OK (incluye sensores.0001_initial)
python manage.py test -v 2             # Ran 0 tests ... NO TESTS RAN
```

### Pruebas nuevas (48 casos)

```powershell
copy <repo>\entrega-eva3\pruebas\django\tests_eva3.py <copia>\django\sensores\tests_eva3.py
python manage.py test sensores.tests_eva3 -v 2
```
Resultado (`evidencias/logs/django_tests_eva3.txt`):
```
Ran 48 tests in 7.787s
FAILED (failures=18)
[MEDICION P018] 300 POST en 0.19 s (1561.0 req/s, cliente de pruebas en proceso)
```
Fallan: P008, P009, P010, P014, P015, P016, P017, P026, P031, P032, P033, P043, P047, P048, P051, P060, P061, P063.

### Prueba en vivo (19 casos)

```powershell
python manage.py migrate
python manage.py shell -c "exec(open(r'<repo>\entrega-eva3\pruebas\django\seed_eva3.py', encoding='utf-8').read())"   # semilla OK
python manage.py runserver 127.0.0.1:8765 --noreload
# en otra terminal:
python smoke_api_live.py http://127.0.0.1:8765
```
Resultado (`evidencias/logs/smoke_live.txt`): `TOTAL 19 OK 13 DISCREPANCIA 6` (L05, L06, L11, L15, L16, L17).
Concurrencia L19: 10 hilos × 20 POST → 200 respuestas 201, 0 errores, 4,39 s.

### Índices y consultas

```powershell
python manage.py shell -c "exec(open(r'<repo>\entrega-eva3\pruebas\django\consultas_orm.py', encoding='utf-8').read())"
```
Resultado en `evidencias/logs/consultas_orm.txt` (RFID con tratamiento: 4 consultas; vaca sana: 2; ingesta con alerta: 3; login: 1).

## 2. App Flutter (versión evaluada)

```powershell
cd <copia>\Flutter
flutter pub get        # Got dependencies!
flutter analyze        # 5 issues found (info: prefer_const_*), exit code 1
flutter test           # 3 pruebas existentes: All tests passed!
copy <repo>\entrega-eva3\pruebas\flutter\eva3_test.dart test\
flutter test test/eva3_test.dart --reporter expanded
```
Resultado (`evidencias/logs/flutter_eva3.txt`): 13 pasan, 5 fallan (F-003, F-014, F-022, F-023, F-035) — `Some tests failed.`

Capturas:
```powershell
copy <repo>\entrega-eva3\pruebas\flutter\capturas_test.dart test\
flutter test test/capturas_test.dart --update-goldens     # escribe test/capturas/*.png
```
Nota: el botón ENTRAR y los ejes del gráfico se ven como bloques por la fuente de pruebas de Flutter.

## 3. Rama Pin-de-Acceso (referencial, no integrada)

```powershell
git archive --format=tar Pin-de-Acceso django Flutter README.md -o pin.tar   # extraído en carpeta aparte
pip install -r django\requirements.txt
python manage.py check ; python manage.py makemigrations --check --dry-run ; python manage.py test -v 2
cd Flutter ; flutter pub get ; flutter analyze ; flutter test
```
Resultados: Django 5/5 OK; `flutter analyze` sin problemas; Flutter 5/7 (fallan "getHumedad24h y ChartPainter…"
y "Flujo completo… login con Pinput"). Logs: `pin_django.txt`, `pin_flutter.txt`.

## 4. Aportes por integrante (git)

```
git shortlog -sn --all --no-merges
     7  Degere                         (Victor Gamboa Leiva)
     3  Juaquin-35                     (Juaquin Álvarez Molina)
     3  LynxLawliet                    (Pedro Caro Villarroel)
     1  Marco Milanca                  (Marco Milanca Pérez)
     1  Victor Gamboa Leiva (Degere)   (Victor Gamboa Leiva)
```

## Limitaciones

- No se ejecutó la app en dispositivo/emulador (sin JDK en el PATH): Firebase en vivo y el modo offline no se validaron.
- Sin acceso a la consola de Firebase: no se revisaron reglas ni datos.
- Rendimiento medido con SQLite y `runserver`: no extrapolable a producción.
- No se reproducen secretos (SECRET_KEY, claves de Firebase, credenciales Wi-Fi del sketch) ni datos de `db.sqlite3`.
