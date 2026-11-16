from unittest.mock import patch
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from .models import Alerta, Animal, CollarRfid, EventoSanitario, LecturaSensor, Rol, Sensor, Tratamiento, Usuario


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
        self.auth_client = APIClient()
        self.auth_client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

    def test_acceso_no_autenticado_bloqueado(self):
        """Verifica que los endpoints protegidos rechacen peticiones sin token JWT."""
        resp = self.client.get("/api/telemetria/")
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_login_pin_invalido_rechazado(self):
        """Verifica validación de PIN de 6 dígitos y rechazo de credenciales incorrectas."""
        resp_Wrong = self.client.post(
            "/api/auth/login-pin/",
            {"email": "admin@moncodairy.cl", "pin": "999999"},
            format="json",
        )
        self.assertEqual(resp_Wrong.status_code, status.HTTP_401_UNAUTHORIZED)

        resp_formato = self.client.post(
            "/api/auth/login-pin/",
            {"email": "admin@moncodairy.cl", "pin": "12ab56"},
            format="json",
        )
        self.assertEqual(resp_formato.status_code, status.HTTP_400_BAD_REQUEST)

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

    @patch("sensores.firebase_service.FirebaseService.obtener_telemetria", return_value=MOCK_TELEMETRIA_RECORDS)
    def test_obtener_telemetria_y_corrales_firebase(self, _mock_fb):
        """Verifica que la API entregue la telemetría de Firebase y el estado de los 20 corrales."""
        resp_tel = self.auth_client.get("/api/telemetria/?limit=10")
        self.assertEqual(resp_tel.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_tel.data["total"], 1)
        self.assertEqual(resp_tel.data["datos"][0]["dispositivo"], "ESP8266_Sensor1")

        resp_corrales = self.auth_client.get("/api/corrales/")
        self.assertEqual(resp_corrales.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_corrales.data["total"], 20)
        corral_1 = resp_corrales.data["corrales"][0]
        self.assertTrue(corral_1["enVivo"])
        self.assertEqual(corral_1["humedad"], 82.0)
        self.assertEqual(corral_1["temperatura"], 8.5)

    @patch("sensores.firebase_service.FirebaseService.obtener_telemetria", return_value=MOCK_TELEMETRIA_RECORDS)
    def test_sincronizar_firebase_con_bd_y_alertas(self, _mock_fb):
        """Verifica la sincronización de lecturas desde Firebase hacia LecturaSensor y Alerta."""
        resp_sync = self.auth_client.post("/api/firebase/sincronizar/", {"limit": 10}, format="json")
        self.assertEqual(resp_sync.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_sync.data["resumen"]["lecturas_locales_creadas"], 2)
        self.assertEqual(resp_sync.data["resumen"]["alertas_generadas"], 2)
        self.assertEqual(Alerta.objects.count(), 2)

    @patch("sensores.firebase_service.FirebaseService.publicar_telemetria", return_value={"id": "-MockPushId"})
    @patch("sensores.firebase_service.FirebaseService.publicar_alerta", return_value="-MockAlertId")
    @patch("sensores.firebase_service.FirebaseService.obtener_ultima_lectura", return_value=MOCK_TELEMETRIA_RECORDS[0])
    def test_ingesta_iot_y_filtro_rango_fisico(self, _m1, _m2, _m3):
        """Verifica ingesta IoT válida, generación de alerta por frío y descarte fuera de rango."""
        sensor = Sensor.objects.create(ubicacion="Ternerera Corral 1", tipo="TEMPERATURA", estado="ACTIVO")

        # Lectura fuera de rango físico (> 45°C)
        resp_invalida = self.auth_client.post(
            "/api/iot/ingesta/",
            {"sensor_id": sensor.id, "valor": 95.0, "unidad": "°C"},
            format="json",
        )
        self.assertEqual(resp_invalida.status_code, status.HTTP_400_BAD_REQUEST)

        # Lectura crítica por frío (< 10°C)
        resp_valida = self.auth_client.post(
            "/api/iot/ingesta/",
            {"sensor_id": sensor.id, "valor": 7.5, "unidad": "°C", "dispositivo": "ESP8266_Sensor1"},
            format="json",
        )
        self.assertEqual(resp_valida.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(resp_valida.data["alertas_generadas"]), 1)
        self.assertEqual(resp_valida.data["alertas_generadas"][0]["tipo_alerta"], "ESTRES_FRIO_TERNERO")

    def test_verificacion_rfid_bloqueo_antibiotico(self):
        """Verifica que el endpoint RFID bloquee la ordeña cuando existe tratamiento con antibiótico."""
        collar = CollarRfid.objects.create(codigo="RFID-VACA-001", activo=True)
        evento = EventoSanitario.objects.create(
            fecha_hora=timezone.now(),
            descripcion="Mastitis clínica",
            gravedad="ALTA",
        )
        animal = Animal.objects.create(
            evento_sanitario=evento,
            collar_rfid=collar,
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

        resp = self.auth_client.post(
            "/api/ordeña/rfid/",
            {"codigo_rfid": "RFID-VACA-001", "bajada": 12},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["bloquear_ordenia"])
        self.assertEqual(resp.data["color"], "ROJO")
