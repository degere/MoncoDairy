"""
Pruebas Eva-3 (AgroSalud Tech) para la API Django `sensores`.

Archivo NUEVO: no modifica codigo de produccion. Para ejecutarlo se copia a
django/sensores/tests_eva3.py en una copia del proyecto y se corre:

    python manage.py test sensores.tests_eva3 -v 2

Cada prueba afirma el comportamiento ESPERADO segun el informe base (HU, RF/RNF
y estandares de seguridad). Si el codigo actual no lo cumple, la prueba FALLA y
ese fallo se documenta como discrepancia en el informe (no se "arregla" la prueba).
El identificador de cada caso (P-xxx) es el que usa el informe.
"""
import datetime
import time

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import (Alerta, Animal, CollarRfid, EventoSanitario, LecturaSensor,
                     Rol, Sensor, Tratamiento, Usuario)

URL_INGESTA = '/api/iot/ingesta/'
URL_RFID = '/api/ordeña/rfid/'
URL_LOGIN = '/api/auth/login-pin/'
URL_REGISTRO = '/api/auth/registro-pin/'
SQLI = "' OR '1'='1"
XSS = "<script>alert('hack')</script>"


class BaseAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.raise_request_exception = False  # un 500 se registra como resultado, no aborta
        self.sensor_t = Sensor.objects.create(ubicacion='Sala de partos', tipo='TEMPERATURA', estado='ACTIVO')
        self.sensor_h = Sensor.objects.create(ubicacion='Ternerera 1', tipo='HUMEDAD', estado='ACTIVO')

    def ingesta(self, sensor_id, valor, unidad):
        return self.client.post(URL_INGESTA, {'sensor_id': sensor_id, 'valor': valor, 'unidad': unidad}, format='json')


# ---------------------------------------------------------------- Ingesta IoT
class IngestaIoTTests(BaseAPITest):
    def test_P001_lectura_normal_se_guarda_sin_alerta(self):
        r = self.ingesta(self.sensor_t.id, 18, '°C')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(LecturaSensor.objects.count(), 1)
        self.assertEqual(Alerta.objects.count(), 0)

    def test_P002_bordes_temperatura_aceptados(self):
        for v in (-20, 45):
            self.assertEqual(self.ingesta(self.sensor_t.id, v, '°C').status_code, 201, v)

    def test_P003_fuera_de_rango_temperatura_rechazado_y_no_guardado(self):
        for v in (-20.01, 45.01, 200):
            self.assertEqual(self.ingesta(self.sensor_t.id, v, '°C').status_code, 400, v)
        self.assertEqual(LecturaSensor.objects.count(), 0)

    def test_P004_bordes_y_fuera_de_rango_humedad(self):
        self.assertEqual(self.ingesta(self.sensor_h.id, 0, '%').status_code, 201)
        self.assertEqual(self.ingesta(self.sensor_h.id, 100, '%').status_code, 201)
        self.assertEqual(self.ingesta(self.sensor_h.id, 100.1, '%').status_code, 400)
        self.assertEqual(self.ingesta(self.sensor_h.id, -0.1, '%').status_code, 400)

    def test_P005_parametros_faltantes(self):
        r = self.client.post(URL_INGESTA, {'sensor_id': self.sensor_t.id}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_P006_valor_no_numerico_o_nan(self):
        self.assertEqual(self.ingesta(self.sensor_t.id, 'abc', '°C').status_code, 400)
        self.assertEqual(self.ingesta(self.sensor_t.id, 'NaN', '°C').status_code, 400)
        self.assertEqual(self.ingesta(self.sensor_h.id, 'Infinity', '%').status_code, 400)

    def test_P007_sensor_inexistente_e_inyeccion_sql(self):
        self.assertEqual(self.ingesta(99999, 18, '°C').status_code, 404)
        self.assertEqual(self.ingesta(SQLI, 18, '°C').status_code, 404)
        self.assertEqual(LecturaSensor.objects.count(), 0)

    def test_P008_unidad_desconocida_debe_rechazarse(self):
        # Estandar 4 del informe base: whitelisting de rangos. 'kg' no es una unidad valida.
        r = self.ingesta(self.sensor_t.id, 99999, 'kg')
        self.assertEqual(r.status_code, 400)

    def test_P009_unidad_desconocida_con_valor_enorme_no_debe_dar_500(self):
        r = self.ingesta(self.sensor_t.id, 1e12, 'kg')
        self.assertNotEqual(r.status_code, 500)
        self.assertEqual(r.status_code, 400)

    def test_P010_xss_en_unidad_debe_rechazarse(self):
        r = self.ingesta(self.sensor_t.id, 18, XSS)
        self.assertEqual(r.status_code, 400)

    def test_P011_alerta_frio_rojo(self):
        self.ingesta(self.sensor_t.id, 9.9, '°C')
        a = Alerta.objects.get()
        self.assertEqual((a.tipo_alerta, a.nivel, a.estado_lectura), ('ESTRES_FRIO_TERNERO', 'ROJO', 'PENDIENTE'))
        self.assertIsNotNone(a.lectura_sensor_id)

    def test_P012_alerta_calor_amarillo_y_borde_25(self):
        self.ingesta(self.sensor_t.id, 25.0, '°C')
        self.assertEqual(Alerta.objects.count(), 0)
        self.ingesta(self.sensor_t.id, 25.1, '°C')
        self.assertEqual(Alerta.objects.get().nivel, 'AMARILLO')

    def test_P013_alerta_humedad_cama_borde_80(self):
        self.ingesta(self.sensor_h.id, 79.9, '%')
        self.assertEqual(Alerta.objects.count(), 0)
        self.ingesta(self.sensor_h.id, 80, '%')
        self.assertEqual(Alerta.objects.get().tipo_alerta, 'CAMAS_CALIENTES_HUMEDAD')

    def test_P014_HU002_una_lectura_aislada_no_debe_alertar(self):
        # HU-002: humedad >= 80 % Y T <= 10 C sostenidas por mas de 2 horas.
        self.ingesta(self.sensor_h.id, 85, '%')
        self.assertEqual(Alerta.objects.count(), 0)

    def test_P015_HU001_calculo_THI_en_patio(self):
        # HU-001 / RF-02: con T = 30 C y HR = 80 % el THI es aprox. 82 (>= 72) y debe existir una alerta THI.
        self.ingesta(self.sensor_t.id, 30, '°C')
        self.ingesta(self.sensor_h.id, 80, '%')
        self.assertTrue(Alerta.objects.filter(tipo_alerta__icontains='THI').exists())

    def test_P016_ingesta_sin_autenticacion_debe_rechazarse(self):
        # Estandar 7 del informe base: solo dispositivos autenticados pueden publicar lecturas.
        r = self.ingesta(self.sensor_t.id, 18, '°C')
        self.assertIn(r.status_code, (401, 403))

    def test_P017_sensor_inactivo_no_debe_aceptar_lecturas(self):
        # Estandar 7: el backend verifica que el sensor exista y este ACTIVO.
        s = Sensor.objects.create(ubicacion='Bodega', tipo='TEMPERATURA', estado='INACTIVO')
        self.assertIn(self.ingesta(s.id, 18, '°C').status_code, (400, 403, 404))

    def test_P018_estres_300_lecturas_secuenciales(self):
        t0 = time.perf_counter()
        codigos = [self.ingesta(self.sensor_t.id, 15 + (i % 10), '°C').status_code for i in range(300)]
        dt = time.perf_counter() - t0
        print(f'\n[MEDICION P018] 300 POST en {dt:.2f} s ({300 / dt:.1f} req/s, cliente de pruebas en proceso)')
        self.assertEqual(codigos.count(201), 300)
        self.assertEqual(LecturaSensor.objects.count(), 300)


# ------------------------------------------------------------ RFID / bloqueo
class RFIDBloqueoTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.collar = CollarRfid.objects.create(codigo='RFID-0001', activo=True)
        self.vaca = Animal.objects.create(collar_rfid=self.collar, fecha_nacimiento=datetime.date(2021, 5, 1), estado='ORDEÑA')

    def rfid(self, codigo, bajada=5):
        return self.client.post(URL_RFID, {'codigo_rfid': codigo, 'bajada': bajada}, format='json')

    def _evento_con_tratamiento(self, fecha_fin=None, bloqueo=True):
        ev = EventoSanitario.objects.create(fecha_hora=timezone.now(), descripcion='Mastitis cuarto AD', gravedad='ALTA')
        Tratamiento.objects.create(evento_sanitario=ev, medicamento='Cefalexina', dosis='10 ml',
                                   fecha_inicio=datetime.date.today() - datetime.timedelta(days=2),
                                   fecha_fin=fecha_fin, bloqueo_leche=bloqueo)
        self.vaca.evento_sanitario = ev
        self.vaca.save()

    def test_P020_codigo_ausente(self):
        self.assertEqual(self.client.post(URL_RFID, {}, format='json').status_code, 400)

    def test_P021_rfid_inexistente(self):
        self.assertEqual(self.rfid('NO-EXISTE').status_code, 404)

    def test_P022_collar_inactivo(self):
        CollarRfid.objects.filter(pk=self.collar.pk).update(activo=False)
        self.assertEqual(self.rfid('RFID-0001').status_code, 404)

    def test_P023_collar_sin_animal(self):
        CollarRfid.objects.create(codigo='RFID-LIBRE', activo=True)
        self.assertEqual(self.rfid('RFID-LIBRE').status_code, 404)

    def test_P024_vaca_sana_habilitada(self):
        r = self.rfid('RFID-0001')
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.data['bloquear_ordenia'], r.data['color']), (False, 'VERDE'))

    def test_P025_tratamiento_activo_bloquea(self):
        self._evento_con_tratamiento(fecha_fin=None)
        r = self.rfid('RFID-0001')
        self.assertEqual((r.status_code, r.data['bloquear_ordenia'], r.data['color']), (200, True, 'ROJO'))

    def test_P026_periodo_de_resguardo_vigente_debe_bloquear(self):
        # Tratamiento con fecha_fin futura: la leche sigue con residuos hasta esa fecha.
        self._evento_con_tratamiento(fecha_fin=datetime.date.today() + datetime.timedelta(days=3))
        self.assertTrue(self.rfid('RFID-0001').data['bloquear_ordenia'])

    def test_P027_tratamiento_terminado_habilita(self):
        self._evento_con_tratamiento(fecha_fin=datetime.date.today() - datetime.timedelta(days=1))
        self.assertFalse(self.rfid('RFID-0001').data['bloquear_ordenia'])

    def test_P028_tratamiento_sin_bloqueo_no_bloquea(self):
        self._evento_con_tratamiento(fecha_fin=None, bloqueo=False)
        self.assertFalse(self.rfid('RFID-0001').data['bloquear_ordenia'])

    def test_P029_inyeccion_sql_en_rfid(self):
        self.assertEqual(self.rfid(SQLI).status_code, 404)

    def test_P030_cliente_no_puede_forzar_desbloqueo(self):
        # Estandar 5: un parametro bloqueo=false enviado por el cliente no altera la regla.
        self._evento_con_tratamiento(fecha_fin=None)
        r = self.client.post(URL_RFID, {'codigo_rfid': 'RFID-0001', 'bajada': 3, 'bloqueo': False,
                                        'bloquear_ordenia': False}, format='json')
        self.assertTrue(r.data['bloquear_ordenia'])

    def test_P031_bajada_fuera_de_rango_1_38(self):
        self.assertEqual(self.rfid('RFID-0001', bajada=99).status_code, 400)

    def test_P032_tratamiento_anterior_no_se_pierde_al_registrar_nuevo_evento(self):
        # Modelo: animal.evento_sanitario es UNA sola FK. Si se registra un evento nuevo (p. ej. cojera),
        # el tratamiento antibiotico vigente del evento anterior deja de considerarse.
        self._evento_con_tratamiento(fecha_fin=None)
        ev2 = EventoSanitario.objects.create(fecha_hora=timezone.now(), descripcion='Cojera leve', gravedad='BAJA')
        self.vaca.evento_sanitario = ev2
        self.vaca.save()
        self.assertTrue(self.rfid('RFID-0001').data['bloquear_ordenia'])

    def test_P033_rfid_sin_autenticacion_debe_rechazarse(self):
        self.assertIn(self.rfid('RFID-0001').status_code, (401, 403))


# ------------------------------------------------------- Autenticacion / RBAC
class AuthPINTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.rol_lechero = Rol.objects.create(nombre='LECHERO')
        self.rol_admin = Rol.objects.create(nombre='ADMINISTRADOR')
        self.ana = Usuario.objects.create(rol=self.rol_lechero, nombre='Ana', email='ana@moncopulli.cl',
                                          password_hash=make_password('482913'), activo=True)

    def login(self, email, pin):
        return self.client.post(URL_LOGIN, {'email': email, 'pin': pin}, format='json')

    def test_P040_registro_valido_hashea_pin(self):
        r = self.client.post(URL_REGISTRO, {'nombre': 'Luis', 'email': 'luis@moncopulli.cl', 'rol': self.rol_lechero.id,
                                            'pin': '135790', 'activo': True}, format='json')
        self.assertEqual(r.status_code, 201)
        u = Usuario.objects.get(email='luis@moncopulli.cl')
        self.assertNotEqual(u.password_hash, '135790')
        self.assertTrue(u.password_hash.startswith(('pbkdf2_sha256$', 'argon2', 'bcrypt')))
        self.assertNotIn('pin', r.data['usuario'])
        self.assertNotIn('password_hash', r.data['usuario'])

    def test_P041_registro_pin_invalido(self):
        for pin in ('12345', '1234567', 'abcdef', '12 456'):
            r = self.client.post(URL_REGISTRO, {'nombre': 'X', 'email': f'x{pin.strip()}@m.cl', 'rol': self.rol_lechero.id,
                                                'pin': pin, 'activo': True}, format='json')
            self.assertEqual(r.status_code, 400, pin)

    def test_P042_registro_email_duplicado_y_rol_inexistente(self):
        r1 = self.client.post(URL_REGISTRO, {'nombre': 'A', 'email': 'ana@moncopulli.cl', 'rol': self.rol_lechero.id,
                                             'pin': '111111', 'activo': True}, format='json')
        r2 = self.client.post(URL_REGISTRO, {'nombre': 'B', 'email': 'b@m.cl', 'rol': 999,
                                             'pin': '111111', 'activo': True}, format='json')
        self.assertEqual((r1.status_code, r2.status_code), (400, 400))

    def test_P043_registro_sin_autenticacion_no_debe_crear_administradores(self):
        r = self.client.post(URL_REGISTRO, {'nombre': 'Intruso', 'email': 'intruso@x.cl', 'rol': self.rol_admin.id,
                                            'pin': '000000', 'activo': True}, format='json')
        self.assertIn(r.status_code, (401, 403))

    def test_P044_login_correcto_devuelve_permisos_del_rol(self):
        r = self.login('ana@moncopulli.cl', '482913')
        self.assertEqual(r.status_code, 200)
        p = r.data['permisos']
        self.assertEqual((p['rol'], p['acceso_ordenia'], p['acceso_admin']), ('LECHERO', True, False))

    def test_P045_login_pin_incorrecto(self):
        self.assertEqual(self.login('ana@moncopulli.cl', '000000').status_code, 401)

    def test_P046_login_usuario_inactivo(self):
        Usuario.objects.filter(pk=self.ana.pk).update(activo=False)
        self.assertEqual(self.login('ana@moncopulli.cl', '482913').status_code, 401)

    def test_P047_mensaje_no_permite_enumerar_usuarios(self):
        r_noexiste = self.login('nadie@moncopulli.cl', '000000')
        r_pinmalo = self.login('ana@moncopulli.cl', '000000')
        self.assertEqual(r_noexiste.data, r_pinmalo.data)

    def test_P048_bloqueo_tras_intentos_fallidos(self):
        # Estandar 8: bloqueo tras 3 intentos (app) / limite de peticiones en API (estandar 10).
        for _ in range(10):
            self.login('ana@moncopulli.cl', '000000')
        r = self.login('ana@moncopulli.cl', '482913')
        self.assertIn(r.status_code, (403, 423, 429))

    def test_P049_inyeccion_sql_en_login(self):
        self.assertEqual(self.login(SQLI, '000000').status_code, 400)
        self.assertEqual(self.login('ana@moncopulli.cl', SQLI[:6]).status_code, 400)

    def test_P050_xss_en_nombre_se_almacena_literal(self):
        r = self.client.post(URL_REGISTRO, {'nombre': XSS, 'email': 'xss@m.cl', 'rol': self.rol_lechero.id,
                                            'pin': '246810', 'activo': True}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r['Content-Type'], 'application/json')
        self.assertEqual(Usuario.objects.get(email='xss@m.cl').nombre, XSS)

    def test_P051_login_entrega_token_para_autorizar_peticiones(self):
        # Estandar 3/9: el backend debe emitir un token (JWT) con expiracion para validar el rol en cada endpoint.
        r = self.login('ana@moncopulli.cl', '482913')
        self.assertTrue(any(k in r.data for k in ('token', 'access', 'access_token')))


# ------------------------------------------------------------- Configuracion
class ConfiguracionTests(TestCase):
    def test_P060_debug_desactivado_fuera_de_desarrollo(self):
        from importlib import import_module
        self.assertFalse(import_module(settings.SETTINGS_MODULE).DEBUG)

    def test_P061_secret_key_no_es_la_generada_por_defecto(self):
        self.assertFalse(settings.SECRET_KEY.startswith('django-insecure-'))

    def test_P062_allowed_hosts_no_es_comodin(self):
        self.assertNotIn('*', settings.ALLOWED_HOSTS)

    def test_P063_rest_framework_define_autenticacion_y_permisos(self):
        conf = getattr(settings, 'REST_FRAMEWORK', {})
        self.assertIn('DEFAULT_PERMISSION_CLASSES', conf)
        self.assertNotIn('rest_framework.permissions.AllowAny', conf.get('DEFAULT_PERMISSION_CLASSES', []))
