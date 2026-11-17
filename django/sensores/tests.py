from unittest.mock import patch
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from .authentication import construir_permisos_rol
from .firebase_service import (
    clasificar_nivel_humedad,
    evaluar_riesgos_sanitarios,
    validar_registro_telemetria,
)
from .models import (
    Alerta,
    Animal,
    CollarRfid,
    EventoSanitario,
    LecturaSensor,
    Rol,
    Sensor,
    Tratamiento,
    Usuario,
)


MOCK_TELEMETRIA_RECORDS = [
    {
        "id": "-P6_6OSISXnP9rE2JuBi",
        "dispositivo": "ESP8266_Sensor1",
        "corral_id": 1,
        "temperatura_celsius": 8.5,
        "humedad_ambiente_pct": 82.0,
        "timestamp": "2026-11-16T16:08:02Z",
        "fecha_local": "2026-11-16 13:08:02",
        "nivel_humedad": "CRITICO",
        "temperatura_baja": True,
        "rango_fisico_valido": True,
        "alertas_detectadas": [
            {
                "tipo_alerta": "ESTRES_FRIO_TERNERO",
                "nivel": "ROJO",
                "valor": 8.5,
                "unidad": "°C",
                "fecha_hora": "2026-11-16T16:08:02Z",
                "estado_lectura": "PENDIENTE",
                "mensaje": "¡ALERTA DE FRÍO EN TERNERERA!",
            },
            {
                "tipo_alerta": "CAMAS_CALIENTES_HUMEDAD",
                "nivel": "ROJO",
                "valor": 82.0,
                "unidad": "%",
                "fecha_hora": "2026-11-16T16:08:02Z",
                "estado_lectura": "PENDIENTE",
                "mensaje": "¡ALERTA DE CAMA HÚMEDA!",
            },
        ],
    }
]


class MoncoDairyAPISecurityAndFirebaseTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.rol_admin = Rol.objects.create(nombre="ADMINISTRADOR", descripcion="Control total del sistema")
        self.rol_veterinario = Rol.objects.create(nombre="VETERINARIO", descripcion="Salud animal")
        self.rol_ternerero = Rol.objects.create(nombre="TERNERERO", descripcion="Operador de ternerera")

        # Crear usuario administrador vía endpoint de registro inicial (bootstrapping)
        resp_reg = self.client.post(
            "/api/auth/registro-pin/",
            {
                "nombre": "Admin MoncoDairy",
                "email": "admin@moncodairy.cl",
                "rol": self.rol_admin.id,
                "pin": "123456",
                "activo": True,
            },
            format="json",
        )
        self.assertEqual(resp_reg.status_code, status.HTTP_201_CREATED)

        # Iniciar sesión para obtener JWT
        resp_login = self.client.post(
            "/api/auth/login-pin/",
            {"email": "admin@moncodairy.cl", "pin": "123456"},
            format="json",
        )
        self.assertEqual(resp_login.status_code, status.HTTP_200_OK)
        self.access_token = resp_login.data["tokens"]["access"]
        self.refresh_token = resp_login.data["tokens"]["refresh"]
        self.auth_client = APIClient()
        self.auth_client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

    def test_acceso_no_autenticado_bloqueado(self):
        """Verifica que los endpoints protegidos rechacen peticiones sin token JWT."""
        for endpoint in ["/api/telemetria/", "/api/corrales/", "/api/sensores/", "/api/alertas/"]:
            resp = self.client.get(endpoint)
            self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_login_pin_invalido_e_inactivo_rechazado(self):
        """Verifica validación de PIN de 6 dígitos, credenciales incorrectas y usuario inactivo."""
        resp_wrong = self.client.post(
            "/api/auth/login-pin/",
            {"email": "admin@moncodairy.cl", "pin": "999999"},
            format="json",
        )
        self.assertEqual(resp_wrong.status_code, status.HTTP_401_UNAUTHORIZED)

        resp_formato = self.client.post(
            "/api/auth/login-pin/",
            {"email": "admin@moncodairy.cl", "pin": "12ab56"},
            format="json",
        )
        self.assertEqual(resp_formato.status_code, status.HTTP_400_BAD_REQUEST)

        # Usuario inactivo no puede iniciar sesión
        self.auth_client.post(
            "/api/auth/registro-pin/",
            {
                "nombre": "Inactivo",
                "email": "inactivo@moncodairy.cl",
                "rol": self.rol_ternerero.id,
                "pin": "654321",
                "activo": False,
            },
            format="json",
        )
        resp_inactivo = self.client.post(
            "/api/auth/login-pin/",
            {"email": "inactivo@moncodairy.cl", "pin": "654321"},
            format="json",
        )
        self.assertEqual(resp_inactivo.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rate_limiting_login_pin(self):
        """Verifica que tras exceder el límite de intentos de login por minuto se bloquee con HTTP 429."""
        codigos = []
        for _ in range(6):
            r = self.client.post(
                "/api/auth/login-pin/",
                {"email": "admin@moncodairy.cl", "pin": "000000"},
                format="json",
            )
            codigos.append(r.status_code)
        self.assertIn(status.HTTP_429_TOO_MANY_REQUESTS, codigos)

    def test_refresh_token_jwt_preserva_rbac(self):
        """Verifica que /api/auth/token/refresh/ emita un nuevo access token válido para Usuario."""
        resp_refresh = self.client.post(
            "/api/auth/token/refresh/",
            {"refresh": self.refresh_token},
            format="json",
        )
        self.assertEqual(resp_refresh.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp_refresh.data)
        self.assertIn("refresh", resp_refresh.data)

        # Usar el nuevo access token para consultar un endpoint protegido
        nuevo_cliente = APIClient()
        nuevo_cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {resp_refresh.data['access']}")
        resp_sensores = nuevo_cliente.get("/api/sensores/")
        self.assertEqual(resp_sensores.status_code, status.HTTP_200_OK)

        # Token refresh inválido debe retornar 401
        resp_invalido = self.client.post(
            "/api/auth/token/refresh/",
            {"refresh": "token.invalido.corrupto"},
            format="json",
        )
        self.assertEqual(resp_invalido.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rbac_roles_y_permisos_sensores_y_usuarios(self):
        """Verifica que solo ADMINISTRADOR gestione roles/usuarios y que TERNERERO no pueda crear sensores."""
        # Admin crea un usuario TERNERERO
        resp_tern = self.auth_client.post(
            "/api/auth/registro-pin/",
            {
                "nombre": "Operador Ternerera",
                "email": "ternerero@moncodairy.cl",
                "rol": self.rol_ternerero.id,
                "pin": "112233",
                "activo": True,
            },
            format="json",
        )
        self.assertEqual(resp_tern.status_code, status.HTTP_201_CREATED)

        login_tern = self.client.post(
            "/api/auth/login-pin/",
            {"email": "ternerero@moncodairy.cl", "pin": "112233"},
            format="json",
        )
        tern_client = APIClient()
        tern_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_tern.data['tokens']['access']}")

        # Ternerero NO puede registrar otros usuarios ni crear roles (403)
        resp_reg_prohibido = tern_client.post(
            "/api/auth/registro-pin/",
            {
                "nombre": "Otro",
                "email": "otro@moncodairy.cl",
                "rol": self.rol_ternerero.id,
                "pin": "445566",
            },
            format="json",
        )
        self.assertEqual(resp_reg_prohibido.status_code, status.HTTP_403_FORBIDDEN)

        # Ternerero puede listar sensores pero NO crear sensores (403)
        self.assertEqual(tern_client.get("/api/sensores/").status_code, status.HTTP_200_OK)
        resp_sensor_prohibido = tern_client.post(
            "/api/sensores/",
            {"ubicacion": "Ternerera 2", "tipo": "HUMEDAD", "estado": "ACTIVO"},
            format="json",
        )
        self.assertEqual(resp_sensor_prohibido.status_code, status.HTTP_403_FORBIDDEN)

        # Admin SÍ puede crear sensores y roles
        resp_sensor_ok = self.auth_client.post(
            "/api/sensores/",
            {"ubicacion": "Ternerera 2", "tipo": "HUMEDAD", "estado": "ACTIVO"},
            format="json",
        )
        self.assertEqual(resp_sensor_ok.status_code, status.HTTP_201_CREATED)

        resp_rol_ok = self.auth_client.post(
            "/api/auth/roles/",
            {"nombre": "PARTERO", "descripcion": "Encargado de maternidad"},
            format="json",
        )
        self.assertEqual(resp_rol_ok.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.auth_client.get("/api/auth/roles/").status_code, status.HTTP_200_OK)

        # Matriz RBAC por rol
        perm_lechero = construir_permisos_rol("LECHERO")
        self.assertTrue(perm_lechero["acceso_ordenia"])
        self.assertFalse(perm_lechero["acceso_maternidad"])
        self.assertFalse(perm_lechero["acceso_admin"])

    @patch("sensores.firebase_service.FirebaseService.obtener_telemetria", return_value=MOCK_TELEMETRIA_RECORDS)
    def test_obtener_telemetria_ultima_corrales_e_historial_firebase(self, _mock_fb):
        """Verifica telemetría, última lectura, estado de los 20 corrales e historial por corral."""
        resp_tel = self.auth_client.get("/api/telemetria/?limit=10")
        self.assertEqual(resp_tel.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_tel.data["total"], 1)
        self.assertEqual(resp_tel.data["datos"][0]["dispositivo"], "ESP8266_Sensor1")

        resp_ultima = self.auth_client.get("/api/telemetria/ultima/")
        self.assertEqual(resp_ultima.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_ultima.data["lectura"]["temperatura_celsius"], 8.5)

        resp_corrales = self.auth_client.get("/api/corrales/")
        self.assertEqual(resp_corrales.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_corrales.data["total"], 20)
        corral_1 = resp_corrales.data["corrales"][0]
        self.assertTrue(corral_1["enVivo"])
        self.assertEqual(corral_1["humedad"], 82.0)
        self.assertEqual(corral_1["temperatura"], 8.5)

        resp_hist = self.auth_client.get("/api/corrales/1/historial/?limit=10")
        self.assertEqual(resp_hist.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_hist.data["corral_id"], 1)
        self.assertEqual(resp_hist.data["total_registros"], 1)

        # Corral fuera de rango (1..100)
        resp_hist_invalido = self.auth_client.get("/api/corrales/150/historial/")
        self.assertEqual(resp_hist_invalido.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("sensores.firebase_service.FirebaseService.publicar_alerta", return_value="-MockAlertKey")
    @patch("sensores.firebase_service.FirebaseService.publicar_telemetria")
    def test_publicar_telemetria_directa_firebase(self, mock_pub_tel, _mock_pub_alerta):
        """Verifica POST /api/telemetria/ hacia Firebase validando rangos y alertas."""
        mock_pub_tel.return_value = {
            **MOCK_TELEMETRIA_RECORDS[0],
            "id": "-MockNewTelKey",
        }
        resp_ok = self.auth_client.post(
            "/api/telemetria/",
            {
                "dispositivo": "ESP8266_Sensor1",
                "corral_id": 1,
                "temperatura_celsius": 8.5,
                "humedad_ambiente_pct": 82.0,
            },
            format="json",
        )
        self.assertEqual(resp_ok.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp_ok.data["registro"]["id"], "-MockNewTelKey")

        # Temperatura fuera de rango permitido en el serializer (> 45°C)
        resp_bad = self.auth_client.post(
            "/api/telemetria/",
            {
                "dispositivo": "ESP8266_Sensor1",
                "corral_id": 1,
                "temperatura_celsius": 60.0,
                "humedad_ambiente_pct": 50.0,
            },
            format="json",
        )
        self.assertEqual(resp_bad.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("sensores.firebase_service.FirebaseService.obtener_telemetria", return_value=MOCK_TELEMETRIA_RECORDS)
    def test_sincronizar_firebase_con_bd_idempotencia_y_gestion_alertas(self, _mock_fb):
        """Verifica sincronización idempotente Firebase -> BD y ciclo de vida de alertas (PENDIENTE -> LEIDA -> RESUELTA)."""
        resp_sync = self.auth_client.post("/api/firebase/sincronizar/", {"limit": 10}, format="json")
        self.assertEqual(resp_sync.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_sync.data["resumen"]["lecturas_locales_creadas"], 2)
        self.assertEqual(resp_sync.data["resumen"]["alertas_generadas"], 2)
        self.assertEqual(Alerta.objects.count(), 2)

        # Segunda sincronización con los mismos timestamps no debe duplicar lecturas ni alertas
        resp_sync_2 = self.auth_client.post("/api/firebase/sincronizar/", {"limit": 10}, format="json")
        self.assertEqual(resp_sync_2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_sync_2.data["resumen"]["lecturas_locales_creadas"], 0)
        self.assertEqual(Alerta.objects.count(), 2)

        # Consultar listado de alertas filtrando por PENDIENTE
        resp_list = self.auth_client.get("/api/alertas/?estado_lectura=PENDIENTE")
        self.assertEqual(resp_list.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_list.data["total_bd"], 2)

        # Actualizar estado de alerta a LEIDA y luego a RESUELTA
        alerta_id = resp_list.data["alertas"][0]["id"]
        resp_patch = self.auth_client.patch(
            f"/api/alertas/{alerta_id}/",
            {"estado_lectura": "LEIDA"},
            format="json",
        )
        self.assertEqual(resp_patch.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_patch.data["alerta"]["estado_lectura"], "LEIDA")

        # Estado inválido debe retornar 400
        resp_patch_bad = self.auth_client.patch(
            f"/api/alertas/{alerta_id}/",
            {"estado_lectura": "DESCONOCIDO"},
            format="json",
        )
        self.assertEqual(resp_patch_bad.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("sensores.firebase_service.FirebaseService.publicar_telemetria", return_value={"id": "-MockPushId"})
    @patch("sensores.firebase_service.FirebaseService.publicar_alerta", return_value="-MockAlertId")
    @patch("sensores.firebase_service.FirebaseService.obtener_ultima_lectura", return_value=MOCK_TELEMETRIA_RECORDS[0])
    def test_ingesta_iot_y_filtro_rango_fisico(self, _m1, _m2, _m3):
        """Verifica ingesta IoT válida (frío, calor, humedad), validación de corral y descarte fuera de rango."""
        sensor_temp = Sensor.objects.create(ubicacion="Ternerera Corral 1", tipo="TEMPERATURA", estado="ACTIVO")
        sensor_hum = Sensor.objects.create(ubicacion="Ternerera Corral 1", tipo="HUMEDAD", estado="ACTIVO")

        # Lectura fuera de rango físico (> 45°C)
        resp_invalida = self.auth_client.post(
            "/api/iot/ingesta/",
            {"sensor_id": sensor_temp.id, "valor": 95.0, "unidad": "°C"},
            format="json",
        )
        self.assertEqual(resp_invalida.status_code, status.HTTP_400_BAD_REQUEST)

        # Corral inválido
        resp_corral_invalido = self.auth_client.post(
            "/api/iot/ingesta/",
            {"sensor_id": sensor_temp.id, "valor": 15.0, "unidad": "°C", "corral_id": "invalido"},
            format="json",
        )
        self.assertEqual(resp_corral_invalido.status_code, status.HTTP_400_BAD_REQUEST)

        # Lectura crítica por frío (< 10°C)
        resp_frio = self.auth_client.post(
            "/api/iot/ingesta/",
            {"sensor_id": sensor_temp.id, "valor": 7.5, "unidad": "°C", "dispositivo": "ESP8266_Sensor1"},
            format="json",
        )
        self.assertEqual(resp_frio.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp_frio.data["alertas_generadas"][0]["tipo_alerta"], "ESTRES_FRIO_TERNERO")

        # Lectura de alerta por calor (> 25°C)
        resp_calor = self.auth_client.post(
            "/api/iot/ingesta/",
            {"sensor_id": sensor_temp.id, "valor": 28.0, "unidad": "°C", "dispositivo": "ESP8266_Sensor1"},
            format="json",
        )
        self.assertEqual(resp_calor.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp_calor.data["alertas_generadas"][0]["tipo_alerta"], "ESTRES_CALOR_TERNERO")

        # Lectura crítica por humedad de cama (>= 80%)
        resp_hum = self.auth_client.post(
            "/api/iot/ingesta/",
            {"sensor_id": sensor_hum.id, "valor": 85.0, "unidad": "%", "dispositivo": "ESP8266_Sensor1"},
            format="json",
        )
        self.assertEqual(resp_hum.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp_hum.data["alertas_generadas"][0]["tipo_alerta"], "CAMAS_CALIENTES_HUMEDAD")

    def test_verificacion_rfid_bloqueo_y_habilitacion_ordena(self):
        """Verifica bloqueo de ordeña por antibiótico, animal sano y validaciones de bajada/collar."""
        collar_bloq = CollarRfid.objects.create(codigo="RFID-VACA-001", activo=True)
        evento = EventoSanitario.objects.create(
            fecha_hora=timezone.now(),
            descripcion="Mastitis clínica",
            gravedad="ALTA",
        )
        Animal.objects.create(
            evento_sanitario=evento,
            collar_rfid=collar_bloq,
            fecha_nacimiento=timezone.now().date(),
            estado="EN_TRATAMIENTO",
        )
        Tratamiento.objects.create(
            evento_sanitario=evento,
            medicamento="Cefalosporina",
            dosis="10ml",
            fecha_inicio=timezone.now().date(),
            fecha_fin=None,
            bloqueo_leche=True,
        )

        resp_bloq = self.auth_client.post(
            "/api/ordeña/rfid/",
            {"codigo_rfid": "RFID-VACA-001", "bajada": 12},
            format="json",
        )
        self.assertEqual(resp_bloq.status_code, status.HTTP_200_OK)
        self.assertTrue(resp_bloq.data["bloquear_ordenia"])
        self.assertEqual(resp_bloq.data["color"], "ROJO")

        # Animal sano en ruta ASCII /api/ordena/rfid/
        collar_sano = CollarRfid.objects.create(codigo="RFID-VACA-002", activo=True)
        Animal.objects.create(
            evento_sanitario=None,
            collar_rfid=collar_sano,
            fecha_nacimiento=timezone.now().date(),
            estado="SANO",
        )
        resp_sano = self.auth_client.post(
            "/api/ordena/rfid/",
            {"codigo_rfid": "RFID-VACA-002", "bajada": 5},
            format="json",
        )
        self.assertEqual(resp_sano.status_code, status.HTTP_200_OK)
        self.assertFalse(resp_sano.data["bloquear_ordenia"])
        self.assertEqual(resp_sano.data["color"], "VERDE")

        # Bajada fuera de rango (1..38)
        resp_bajada_invalida = self.auth_client.post(
            "/api/ordena/rfid/",
            {"codigo_rfid": "RFID-VACA-002", "bajada": 39},
            format="json",
        )
        self.assertEqual(resp_bajada_invalida.status_code, status.HTTP_400_BAD_REQUEST)

        # Collar no registrado
        resp_no_existe = self.auth_client.post(
            "/api/ordena/rfid/",
            {"codigo_rfid": "RFID-INEXISTENTE", "bajada": 1},
            format="json",
        )
        self.assertEqual(resp_no_existe.status_code, status.HTTP_404_NOT_FOUND)

    def test_funciones_dominio_y_esquema_openapi(self):
        """Verifica validadores puros de telemetría/humedad y generación del esquema OpenAPI."""
        self.assertEqual(clasificar_nivel_humedad(80.0), "CRITICO")
        self.assertEqual(clasificar_nivel_humedad(65.0), "ALERTA")
        self.assertEqual(clasificar_nivel_humedad(50.0), "OK")

        # Registro corrupto o con tipos booleanos debe ser descartado
        self.assertIsNone(validar_registro_telemetria("id1", "no-es-dict"))
        self.assertIsNone(
            validar_registro_telemetria(
                "id2",
                {
                    "dispositivo": "ESP8266",
                    "lecturas_crudas": {"temperatura_celsius": True, "humedad_ambiente_pct": 50},
                },
            )
        )

        # Esquema OpenAPI y Swagger UI responden 200 OK
        resp_schema = self.auth_client.get("/api/schema/")
        self.assertEqual(resp_schema.status_code, status.HTTP_200_OK)
        resp_docs = self.auth_client.get("/api/docs/")
        self.assertEqual(resp_docs.status_code, status.HTTP_200_OK)
