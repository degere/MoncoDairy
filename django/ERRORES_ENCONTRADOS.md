# Reporte de Errores Encontrados y Solucionados — Backend MoncoDairy

Durante la auditoría y ejecución de pruebas integrales sobre el backend en `django/`, se detectaron y corrigieron **6 problemas críticos y de configuración** que impedían ejecutar las pruebas, refrescar sesiones JWT o validar ciertos parámetros de entrada.

---

## Error 1: Paquetes faltantes en el entorno virtual (`ModuleNotFoundError: No module named 'firebase_admin'`)
- **Severidad**: Crítica (Bloqueante al iniciar el proyecto).
- **Archivo afectado**: Entorno virtual `django/venv` vs [requirements.txt](file:///home/marco/Documentos/GitHub/MoncoDairy/django/requirements.txt).
- **Síntoma**:
  Al ejecutar `./venv/bin/python manage.py check` o `manage.py test`, Django fallaba inmediatamente al cargar `config/settings.py`:
  ```text
  ModuleNotFoundError: No module named 'firebase_admin'
  ```
- **Causa raíz**:
  El entorno virtual `django/venv` solo tenía instaladas 7 librerías iniciales (`Django`, `django-environ`, `psycopg2-binary`, `asgiref`, `sqlparse`, `tzdata`, `pip`) y no se habían instalado los paquetes añadidos posteriormente en `requirements.txt` (`firebase_admin`, `djangorestframework`, `djangorestframework_simplejwt`, `drf-spectacular`, `django-cors-headers`, `django-filter`, etc.).
- **Solución aplicada**:
  Se ejecutó `./venv/bin/pip install -r requirements.txt`, dejando instaladas las 53 dependencias requeridas.

---

## Error 2: Caída por falta de `SECRET_KEY` en `.env` (`ImproperlyConfigured: Set the SECRET_KEY environment variable`)
- **Severidad**: Alta (Bloqueante en entornos locales).
- **Archivos afectados**: [settings.py](file:///home/marco/Documentos/GitHub/MoncoDairy/django/config/settings.py#L31-L34) y `.env`.
- **Síntoma**:
  Al ejecutar cualquier comando de `manage.py`, se producía el error:
  ```text
  django.core.exceptions.ImproperlyConfigured: Set the SECRET_KEY environment variable
  ```
- **Causa raíz**:
  El archivo `django/.env` local solo definía `DATABASE_URL=...`, mientras que `settings.py` exigía `SECRET_KEY = env('SECRET_KEY')` sin un valor por defecto de respaldo para desarrollo/pruebas.
- **Solución aplicada**:
  En [settings.py](file:///home/marco/Documentos/GitHub/MoncoDairy/django/config/settings.py#L31-L34) se definió un valor por defecto seguro para desarrollo local cuando la variable no está presente en `.env`.

---

## Error 3: Fallo de todas las pruebas (`AssertionError: 301 != 201`) por `SECURE_SSL_REDIRECT=True` y conexión a BD remota en tests
- **Severidad**: Alta (Rompía el 100% de la suite de tests y peticiones HTTP locales sin TLS).
- **Archivo afectado**: [settings.py](file:///home/marco/Documentos/GitHub/MoncoDairy/django/config/settings.py#L94-L110) y [settings.py](file:///home/marco/Documentos/GitHub/MoncoDairy/django/config/settings.py#L202-L208).
- **Síntoma**:
  Al correr `python manage.py test`, los 7 tests originales fallaban en `setUp` con:
  ```text
  AssertionError: 301 != 201
  ```
- **Causa raíz**:
  1. `DEBUG` tenía como valor por defecto `False`. Al ser `not DEBUG`, se activaba `SECURE_SSL_REDIRECT = True`, haciendo que `SecurityMiddleware` redirigiera todas las peticiones HTTP del `APIClient` de pruebas a `https://` con código `301 Moved Permanently`.
  2. Además, al tener `DATABASE_URL` apuntando al pooler remoto de Supabase (`:6543`) en `.env`, el runner de tests intentaba crear una base de datos de prueba en el pooler remoto y utilizaba el hasher lento PBKDF2 (~35 segundos por corrida).
- **Solución aplicada**:
  En [settings.py](file:///home/marco/Documentos/GitHub/MoncoDairy/django/config/settings.py) se detectó la ejecución de pruebas (`RUNNING_TESTS = 'test' in sys.argv`) para usar automáticamente SQLite en memoria (`:memory:`), `MD5PasswordHasher` en tests (reduciendo el tiempo de 34.3s a **0.6s**) y mantener `SECURE_SSL_REDIRECT = False` por defecto salvo que se habilite explícitamente en producción.

---

## Error 4: Error 500 (`User.DoesNotExist`) al refrescar token JWT en `/api/auth/token/refresh/`
- **Severidad**: Crítica (Rompía la renovación de sesión JWT de la aplicación móvil/web).
- **Archivos afectados**: [urls.py](file:///home/marco/Documentos/GitHub/MoncoDairy/django/sensores/urls.py#L40) y [views.py](file:///home/marco/Documentos/GitHub/MoncoDairy/django/sensores/views.py#L611-L645).
- **Síntoma**:
  Al enviar el token `refresh` emitido por `/api/auth/login-pin/` hacia `POST /api/auth/token/refresh/`, el servidor lanzaba una excepción no controlada (HTTP 500):
  ```text
  django.contrib.auth.models.User.DoesNotExist: User matching query does not exist.
  ```
- **Causa raíz**:
  El endpoint `/api/auth/token/refresh/` usaba `TokenRefreshView` estándar de `rest_framework_simplejwt`. Con `ROTATE_REFRESH_TOKENS = True`, SimpleJWT busca el `user_id` del token dentro de la tabla `auth_user` de Django (`django.contrib.auth.models.User`) en vez del modelo propio `sensores.models.Usuario`. Además, la rotación estándar descartaba los claims personalizados (`usuario_id`, `email`, `nombre`, `rol`, `permisos`).
- **Solución aplicada**:
  Se creó la vista [RefreshTokenPINAPIView](file:///home/marco/Documentos/GitHub/MoncoDairy/django/sensores/views.py#L611-L645) y el serializador [RefreshTokenPINSerializer](file:///home/marco/Documentos/GitHub/MoncoDairy/django/sensores/serializers.py#L102-L103), que validan criptográficamente el `RefreshToken`, comprueban que el usuario exista y siga `activo=True` en la tabla `usuario`, y emiten un nuevo par de tokens `access` y `refresh` conservando todos los permisos RBAC.

---

## Error 5: Error 500 (`ValueError` / `TypeError`) en `/api/iot/ingesta/` ante `corral_id` inválido o fuera de rango
- **Severidad**: Media (Falta de validación de entrada en ingesta IoT).
- **Archivo afectado**: [views.py](file:///home/marco/Documentos/GitHub/MoncoDairy/django/sensores/views.py#L51-L67).
- **Síntoma**:
  Si una petición a `POST /api/iot/ingesta/` enviaba un `corral_id` no numérico (ej. `"corral_id": "abc"` o `null`) o fuera del rango permitido por las reglas de Firebase (`1..100`), la línea `corral_id = int(data.get('corral_id', 1))` lanzaba `ValueError`/`TypeError` sin capturar (HTTP 500) o enviaba un ID inválido a Firebase.
- **Solución aplicada**:
  Se envolvió la conversión de `corral_id` en un bloque `try/except (TypeError, ValueError)` y se validó que cumpla `1 <= corral_id <= 100`, devolviendo `HTTP 400 Bad Request` con un mensaje descriptivo cuando el dato es inválido.

---

## Error 6: Errores y advertencias al generar el esquema OpenAPI (`/api/schema/`) con `drf-spectacular`
- **Severidad**: Baja (Documentación OpenAPI / Swagger incompleta).
- **Archivos afectados**: [authentication.py](file:///home/marco/Documentos/GitHub/MoncoDairy/django/sensores/authentication.py#L132-L146), [serializers.py](file:///home/marco/Documentos/GitHub/MoncoDairy/django/sensores/serializers.py#L106-L118) y [views.py](file:///home/marco/Documentos/GitHub/MoncoDairy/django/sensores/views.py).
- **Síntoma**:
  Al ejecutar `python manage.py spectacular --validate`, se reportaban **22 errores y advertencias** indicando:
  - `Warning: could not resolve authenticator UsuarioPINJWTAuthentication`
  - `Error: unable to guess serializer` en las vistas basadas en `APIView`.
- **Solución aplicada**:
  - Se registró la extensión `UsuarioPINJWTAuthenticationScheme(OpenApiAuthenticationExtension)` en [authentication.py](file:///home/marco/Documentos/GitHub/MoncoDairy/django/sensores/authentication.py#L132-L146).
  - Se declararon los `serializer_class` correspondientes en las vistas de [views.py](file:///home/marco/Documentos/GitHub/MoncoDairy/django/sensores/views.py), reduciendo los errores de esquema OpenAPI a **0**.
