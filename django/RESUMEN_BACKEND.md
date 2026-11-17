# Resumen y Verificación del Backend — MoncoDairy API

## 1. Arquitectura General
El backend de **MoncoDairy** está construido con **Django 6.1** y **Django REST Framework (DRF)** bajo una arquitectura híbrida que combina:
- **Base de Datos Relacional Transaccional** (`PostgreSQL` en producción vía Supabase / `SQLite` en desarrollo y pruebas locales) para el control sanitario, usuarios, roles, trazabilidad de collares RFID y alertas.
- **Firebase Realtime Database y Cloud Firestore** (`appmoncopullisensores`) para la ingesta y lectura en tiempo real de nodos IoT (`ESP8266 + DHT22`) instalados en las ternereras y corrales (`/telemetria`, `/alertas`, `/corrales`).
- **Seguridad API**: Autenticación personalizada por **PIN de 6 dígitos + JWT** (`access` y `refresh`), control de acceso basado en roles (**RBAC**), limitación de tasa (**Rate Limiting / Throttling**) contra fuerza bruta y documentación **OpenAPI 3.0 / Swagger**.

---

## 2. Estructura de Archivos Clave
- [settings.py](file:///home/marco/Documentos/GitHub/MoncoDairy/django/config/settings.py): Configuración central de Django, DRF, SimpleJWT, CORS, cabeceras de seguridad OWASP, Throttling e inicialización de Firebase.
- [models.py](file:///home/marco/Documentos/GitHub/MoncoDairy/django/sensores/models.py): 10 modelos relacionales del dominio lechero.
- [firebase_service.py](file:///home/marco/Documentos/GitHub/MoncoDairy/django/sensores/firebase_service.py): Cliente unificado para Firebase Realtime Database (Admin SDK y REST OAuth2), validadores de esquema/rango y motor de riesgos sanitarios.
- [authentication.py](file:///home/marco/Documentos/GitHub/MoncoDairy/django/sensores/authentication.py) y [permissions.py](file:///home/marco/Documentos/GitHub/MoncoDairy/django/sensores/permissions.py): Autenticación JWT sobre el modelo operativo `Usuario` y permisos según el organigrama del fundo.
- [views.py](file:///home/marco/Documentos/GitHub/MoncoDairy/django/sensores/views.py), [serializers.py](file:///home/marco/Documentos/GitHub/MoncoDairy/django/sensores/serializers.py) y [urls.py](file:///home/marco/Documentos/GitHub/MoncoDairy/django/sensores/urls.py): Endpoints REST y validaciones de entrada/salida.
- [tests.py](file:///home/marco/Documentos/GitHub/MoncoDairy/django/sensores/tests.py): Suite completa de pruebas automatizadas del backend.
- [ERRORES_ENCONTRADOS.md](file:///home/marco/Documentos/GitHub/MoncoDairy/django/ERRORES_ENCONTRADOS.md): Reporte detallado de todos los errores detectados y corregidos durante las pruebas.

---

## 3. Modelos de Datos (`sensores/models.py`)
| Modelo | Tabla BD | Propósito Principal |
| :--- | :--- | :--- |
| `Rol` | `rol` | Define los cargos del fundo (`ADMINISTRADOR`, `VETERINARIO`, `PARTERO`, `TERNERERO`, `LECHERO`). |
| `Usuario` | `usuario` | Operadores y administradores autenticados mediante PIN de 6 dígitos hasheado (`password_hash`). |
| `RegistroOffline` | `registro_offline` | Control de sincronización de operaciones registradas sin conexión en terreno. |
| `EventoSanitario` | `evento_sanitario` | Historial clínico de enfermedades o eventos de salud animal (ej. mastitis). |
| `Tratamiento` | `tratamiento` | Medicación activa/histórica asociada a un evento sanitario; incluye bandera `bloqueo_leche`. |
| `CollarRfid` | `collar_rfid` | Inventario de collares electrónicos RFID (`codigo` único y estado `activo`). |
| `Animal` | `animal` | Vincula cada bovino con su `CollarRfid` (1 a 1) y su `EventoSanitario`. |
| `Sensor` | `sensor` | Inventario de sensores físicos (`TEMPERATURA`, `HUMEDAD`, etc.) y su ubicación. |
| `LecturaSensor` | `lectura_sensor` | Serie histórica local de lecturas validadas (`valor`, `unidad`, `fecha_hora`). |
| `Alerta` | `alerta` | Alertas sanitarias (`ROJO`, `AMARILLO`) con ciclo de gestión (`PENDIENTE` -> `LEIDA` -> `RESUELTA`). |

---

## 4. Resumen Rápido de Endpoints REST

### Autenticación y Roles (PIN + JWT + RBAC)
| Método | Endpoint | Acceso | Descripción |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/auth/login-pin/` | Público (Throttle `5/min`) | Valida `email` + `pin` (6 dígitos) y retorna tokens JWT (`access`, `refresh`) y permisos RBAC. |
| `POST` | `/api/auth/registro-pin/` | Admin (o 1er usuario) | Registra un usuario operativo hasheando su PIN de 6 dígitos. |
| `POST` | `/api/auth/token/refresh/` | Público (con `refresh`) | Rota y emite nuevos tokens JWT verificando que el usuario siga activo. |
| `GET/POST` | `/api/auth/roles/` | Admin (o bootstrapping) | Lista o crea roles del organigrama. |

### Telemetría, Corrales y Sincronización Firebase
| Método | Endpoint | Acceso | Descripción |
| :--- | :--- | :--- | :--- |
| `GET/POST` | `/api/telemetria/` | JWT Autenticado | Consulta las últimas lecturas de `/telemetria` en Firebase o publica un nuevo registro validado. |
| `GET` | `/api/telemetria/ultima/` | JWT Autenticado | Retorna la lectura válida más reciente en vivo desde Firebase. |
| `POST` | `/api/firebase/sincronizar/` | JWT Autenticado | Sincroniza de forma idempotente `/telemetria` de Firebase hacia `Sensor`, `LecturaSensor` y `Alerta`. |
| `GET` | `/api/corrales/` | JWT Autenticado | Entrega el estado de los 20 corrales combinando lecturas en vivo de Firebase y valores base. |
| `GET` | `/api/corrales/<id>/historial/` | JWT Autenticado | Devuelve series históricas de temperatura y humedad de un corral (`1..100`). |

### Sensores, Ingesta IoT, Alertas y Ordeña RFID
| Método | Endpoint | Acceso | Descripción |
| :--- | :--- | :--- | :--- |
| `GET/POST` | `/api/sensores/` | `GET`: JWT / `POST`: Admin o Vet | Lista sensores registrados o inscribe uno nuevo. |
| `POST` | `/api/iot/ingesta/` | JWT (Throttle `120/min`) | Recibe lecturas IoT, filtra rangos físicos, guarda en BD, genera alertas y publica en Firebase. |
| `GET` | `/api/alertas/` | JWT Autenticado | Lista alertas de la BD (filtrable por `?estado_lectura=`) junto con alertas activas en Firebase. |
| `PATCH` | `/api/alertas/<id>/` | JWT Autenticado | Actualiza el `estado_lectura` (`PENDIENTE`, `LEIDA`, `RESUELTA`) de una alerta. |
| `POST` | `/api/ordeña/rfid/` o `/api/ordena/rfid/` | JWT Autenticado | Verifica el collar RFID en las bajadas `1..38` y bloquea la ordeña (`ROJO`) si hay antibióticos activos. |
| `GET` | `/api/schema/` y `/api/docs/` | JWT Autenticado | Esquema OpenAPI 3.0 y documentación interactiva Swagger UI. |

---

## 5. Reglas de Negocio y Motor Sanitario
1. **Filtro de Rango Físico en Ternerera**:
   - **Temperatura válida**: `-20.0 °C` a `45.0 °C` (lecturas fuera de rango se descartan con `HTTP 400`).
   - **Humedad válida**: `0.0 %` a `100.0 %`.
2. **Umbrales de Alertas Sanitarias Automáticas**:
   - `ESTRES_FRIO_TERNERO` (**ROJO**): Temperatura `< 10.0 °C` (riesgo de hipotermia/neumonía neonatal).
   - `ESTRES_CALOR_TERNERO` (**AMARILLO**): Temperatura `> 25.0 °C` (verificar ventilación e hidratación).
   - `CAMAS_CALIENTES_HUMEDAD` (**ROJO**): Humedad `>= 80.0 %` (recambio urgente de cama de paja).
3. **Bloqueo en Sala de Ordeña (RFID)**:
   - Si el animal asociado al collar RFID activo posee un `Tratamiento` con `bloqueo_leche=True` y `fecha_fin=None`, el endpoint responde `bloquear_ordenia: true` y `color: "ROJO"`.

---

## 6. Ejecución de Pruebas (`11/11 OK`)
```bash
cd django
./venv/bin/python manage.py check
./venv/bin/python manage.py test sensores -v 2
```
- `test_acceso_no_autenticado_bloqueado`: **OK**
- `test_login_pin_invalido_e_inactivo_rechazado`: **OK**
- `test_rate_limiting_login_pin`: **OK**
- `test_refresh_token_jwt_preserva_rbac`: **OK**
- `test_rbac_roles_y_permisos_sensores_y_usuarios`: **OK**
- `test_obtener_telemetria_ultima_corrales_e_historial_firebase`: **OK**
- `test_publicar_telemetria_directa_firebase`: **OK**
- `test_sincronizar_firebase_con_bd_idempotencia_y_gestion_alertas`: **OK**
- `test_ingesta_iot_y_filtro_rango_fisico`: **OK**
- `test_verificacion_rfid_bloqueo_y_habilitacion_ordena`: **OK**
- `test_funciones_dominio_y_esquema_openapi`: **OK**
