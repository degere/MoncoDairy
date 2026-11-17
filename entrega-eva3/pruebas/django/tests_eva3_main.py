"""
Pruebas Eva-3 (AgroSalud Tech) para la API Django `sensores`, version `main` + Flutter.

Archivo NUEVO: no modifica codigo de produccion. Se copia a django/sensores/tests_eva3_main.py
en una copia del proyecto y se corre:

    python manage.py test sensores.tests_eva3_main -v 2

Alcance vigente acordado con el cliente: HU-002 (alertas de camas calientes), HU-005 (RBAC) y
HU-006 (offline, que en el backend solo implica sesion/refresh). Cada prueba afirma el comportamiento
ESPERADO segun el informe base (RF/RNF y estandares de seguridad). Si el codigo actual no lo cumple, la
prueba FALLA y ese fallo se documenta como discrepancia (no se "arregla" la prueba).
Firebase se reemplaza por un doble de prueba: ninguna prueba escribe en la base real.
"""
import time
from unittest.mock import MagicMock, patch

from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

import config.settings as cfg
from .models import Alerta, LecturaSensor, Rol, Sensor, Usuario

URL_INGESTA = '/api/iot/ingesta/'
URL_LOGIN = '/api/auth/login-pin/'
URL_REGISTRO = '/api/auth/registro-pin/'
URL_REFRESH = '/api/auth/token/refresh/'
URL_SENSORES = '/api/sensores/'
URL_ROLES = '/api/auth/roles/'
URL_ALERTAS = '/api/alertas/'
SQLI = "' OR '1'='1"
XSS = "<script>alert('hack')</script>"
PIN = '482913'


def _firebase_falso():
    fb = MagicMock()
    fb.obtener_ultima_lectura.return_value = None
    fb.publicar_telemetria.return_value = {'id': 'REG-PRUEBA'}
    fb.publicar_alerta.return_value = 'ALERTA-PRUEBA'
    return fb


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.cli = APIClient()
        self.cli.raise_request_exception = False  # un 500 se registra como resultado, no aborta
        self.roles = {n: Rol.objects.create(nombre=n, descripcion=n) for n in
                      ('ADMINISTRADOR', 'VETERINARIO', 'TERNERERO', 'LECHERO')}
        self.usuarios = {}
        for n, rol in self.roles.items():
            self.usuarios[n] = Usuario.objects.create(
                rol=rol, nombre=f'Usuario {n}', email=f'{n.lower()}@prueba.cl',
                password_hash=make_password(PIN), activo=True)
        self.sensor_t = Sensor.objects.create(ubicacion='Ternerera 1', tipo='TEMPERATURA', estado='ACTIVO')
        self.sensor_h = Sensor.objects.create(ubicacion='Ternerera 1', tipo='HUMEDAD', estado='ACTIVO')
        self.fb = _firebase_falso()
        p = patch('sensores.views.FirebaseService', return_value=self.fb)
        p.start()
        self.addCleanup(p.stop)

    def login(self, rol, pin=PIN):
        r = self.cli.post(URL_LOGIN, {'email': f'{rol.lower()}@prueba.cl', 'pin': pin}, format='json')
        return r

    def cliente(self, rol='TERNERERO'):
        """Cliente ya autenticado mediante el endpoint real de login."""
        r = self.login(rol)
        assert r.status_code == 200, r.content
        c = APIClient()
        c.raise_request_exception = False
        c.credentials(HTTP_AUTHORIZATION='Bearer ' + r.json()['tokens']['access'])
        return c

    def ingesta(self, sensor, valor, unidad, rol='TERNERERO', **extra):
        datos = {'sensor_id': sensor.id, 'valor': valor, 'unidad': unidad, **extra}
        return self.cliente(rol).post(URL_INGESTA, datos, format='json')


# =========================================================== HU-002 / ingesta
class AlertasIngestaTests(Base):
    def test_M001_lectura_normal_se_guarda_sin_alerta(self):
        r = self.ingesta(self.sensor_t, 18, '°C')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(LecturaSensor.objects.count(), 1)
        self.assertEqual(Alerta.objects.count(), 0)

    def test_M002_bordes_temperatura_aceptados(self):
        for v in (-20, 45):
            self.assertEqual(self.ingesta(self.sensor_t, v, '°C').status_code, 201, v)

    def test_M003_fuera_de_rango_temperatura_rechazado_y_no_guardado(self):
        for v in (-20.01, 45.01, 200):
            self.assertEqual(self.ingesta(self.sensor_t, v, '°C').status_code, 400, v)
        self.assertEqual(LecturaSensor.objects.count(), 0)

    def test_M004_bordes_y_fuera_de_rango_humedad(self):
        self.assertEqual(self.ingesta(self.sensor_h, 0, '%').status_code, 201)
        self.assertEqual(self.ingesta(self.sensor_h, 100, '%').status_code, 201)
        self.assertEqual(self.ingesta(self.sensor_h, 100.1, '%').status_code, 400)
        self.assertEqual(self.ingesta(self.sensor_h, -0.1, '%').status_code, 400)

    def test_M005_parametros_faltantes_o_no_numericos(self):
        c = self.cliente()
        self.assertEqual(c.post(URL_INGESTA, {'sensor_id': self.sensor_t.id}, format='json').status_code, 400)
        for malo in ('abc', 'NaN'):
            self.assertEqual(self.ingesta(self.sensor_t, malo, '°C').status_code, 400, malo)
        self.assertEqual(self.ingesta(self.sensor_h, 'Infinity', '%').status_code, 400)

    def test_M006_sensor_inexistente_e_inyeccion_sql(self):
        c = self.cliente()
        for sid in (99999, SQLI):
            r = c.post(URL_INGESTA, {'sensor_id': sid, 'valor': 18, 'unidad': '°C'}, format='json')
            self.assertEqual(r.status_code, 404, sid)
        self.assertEqual(LecturaSensor.objects.count(), 0)

    def test_M007_unidad_desconocida_rechazada(self):
        self.assertEqual(self.ingesta(self.sensor_t, 99999, 'kg').status_code, 400)

    def test_M008_unidad_con_script_debe_rechazarse(self):
        self.assertEqual(self.ingesta(self.sensor_t, 18, XSS).status_code, 400)

    def test_M009_alerta_frio_rojo_bajo_10(self):
        r = self.ingesta(self.sensor_t, 9.9, '°C')
        self.assertEqual(r.status_code, 201)
        a = Alerta.objects.get()
        self.assertEqual((a.tipo_alerta, a.nivel, a.estado_lectura), ('ESTRES_FRIO_TERNERO', 'ROJO', 'PENDIENTE'))
        self.assertIsNotNone(a.lectura_sensor_id)

    def test_M010_alerta_calor_amarillo_borde_25(self):
        self.ingesta(self.sensor_t, 25.0, '°C')
        self.assertEqual(Alerta.objects.count(), 0)
        self.ingesta(self.sensor_t, 25.1, '°C')
        a = Alerta.objects.get()
        self.assertEqual((a.tipo_alerta, a.nivel), ('ESTRES_CALOR_TERNERO', 'AMARILLO'))

    def test_M011_alerta_camas_calientes_borde_80(self):
        self.ingesta(self.sensor_h, 79.9, '%')
        self.assertEqual(Alerta.objects.count(), 0)
        self.ingesta(self.sensor_h, 80, '%')
        a = Alerta.objects.get()
        self.assertEqual((a.tipo_alerta, a.nivel, a.estado_lectura), ('CAMAS_CALIENTES_HUMEDAD', 'ROJO', 'PENDIENTE'))

    def test_M012_HU002_una_sola_lectura_no_debe_alertar(self):
        # El informe base exige humedad >=80 % con temperatura <=10 °C sostenida por mas de 2 horas.
        self.ingesta(self.sensor_h, 85, '%')
        self.assertEqual(Alerta.objects.count(), 0)

    def test_M013_alerta_repetida_no_se_duplica(self):
        # Cinco lecturas consecutivas de 85 % deben mantener una sola alerta pendiente (enfriamiento).
        for _ in range(5):
            self.ingesta(self.sensor_h, 85, '%')
        self.assertEqual(Alerta.objects.filter(tipo_alerta='CAMAS_CALIENTES_HUMEDAD', estado_lectura='PENDIENTE').count(), 1)

    def test_M014_sensor_inactivo_no_acepta_lecturas(self):
        self.sensor_t.estado = 'INACTIVO'
        self.sensor_t.save()
        self.assertIn(self.ingesta(self.sensor_t, 18, '°C').status_code, (400, 403, 404))

    def test_M015_una_magnitud_no_inventa_la_otra_en_telemetria(self):
        self.ingesta(self.sensor_t, 18, '°C')
        kwargs = self.fb.publicar_telemetria.call_args.kwargs
        self.assertNotEqual(kwargs.get('humedad_ambiente_pct'), 60.0, 'se publico una humedad inventada (60 %)')

    def test_M016_ingesta_exige_sesion(self):
        r = APIClient().post(URL_INGESTA, {'sensor_id': self.sensor_t.id, 'valor': 18, 'unidad': '°C'}, format='json')
        self.assertEqual(r.status_code, 401)
        self.assertEqual(LecturaSensor.objects.count(), 0)

    def test_M017_ingesta_solo_para_dispositivos_autorizados(self):
        # Un TERNERERO (rol humano de la app) no deberia poder inyectar lecturas del sensor.
        self.assertIn(self.ingesta(self.sensor_t, 18, '°C', rol='TERNERERO').status_code, (401, 403))

    def test_M018_limite_de_tasa_en_ingesta(self):
        c = self.cliente('ADMINISTRADOR')
        codigos = [c.post(URL_INGESTA, {'sensor_id': self.sensor_t.id, 'valor': 18, 'unidad': '°C'}, format='json').status_code
                   for _ in range(130)]
        self.assertIn(429, codigos)
        self.assertEqual(codigos[:120].count(201), 120)

    def test_M019_estres_lecturas_secuenciales(self):
        c = self.cliente('ADMINISTRADOR')
        t0 = time.perf_counter()
        ok = sum(c.post(URL_INGESTA, {'sensor_id': self.sensor_t.id, 'valor': 18, 'unidad': '°C'}, format='json').status_code == 201
                 for _ in range(100))
        print(f'\n[MEDICION M019] {ok} POST aceptados de 100 en {time.perf_counter() - t0:.2f} s (cliente de pruebas en proceso)')
        self.assertEqual(ok, 100)


# ===================================================== HU-005 / autenticacion
class AutenticacionTests(Base):
    def test_M020_login_correcto_entrega_tokens_y_permisos(self):
        r = self.login('LECHERO')
        self.assertEqual(r.status_code, 200)
        cuerpo = r.json()
        self.assertTrue(cuerpo['tokens']['access'] and cuerpo['tokens']['refresh'])
        self.assertTrue(cuerpo['permisos']['acceso_ordenia'])
        self.assertFalse(cuerpo['permisos']['acceso_admin'])
        texto = r.content.decode()
        self.assertNotIn('password_hash', texto)
        self.assertNotIn('pbkdf2', texto)
        self.assertNotIn(PIN, texto)

    def test_M021_pin_incorrecto_401(self):
        self.assertEqual(self.login('LECHERO', '000000').status_code, 401)

    def test_M022_usuario_inactivo_401(self):
        Usuario.objects.filter(email='lechero@prueba.cl').update(activo=False)
        self.assertEqual(self.login('LECHERO').status_code, 401)

    def test_M023_mensaje_uniforme_email_inexistente_y_pin_incorrecto(self):
        a = self.cli.post(URL_LOGIN, {'email': 'noexiste@prueba.cl', 'pin': PIN}, format='json')
        b = self.cli.post(URL_LOGIN, {'email': 'lechero@prueba.cl', 'pin': '000000'}, format='json')
        self.assertEqual((a.status_code, a.json()), (b.status_code, b.json()))

    def test_M024_inyeccion_sql_en_login(self):
        self.assertEqual(self.cli.post(URL_LOGIN, {'email': SQLI, 'pin': PIN}, format='json').status_code, 400)
        self.assertEqual(self.cli.post(URL_LOGIN, {'email': 'lechero@prueba.cl', 'pin': SQLI}, format='json').status_code, 400)

    def test_M025_formato_de_pin_invalido_400(self):
        for pin in ('12345', '1234567', 'abcdef', '12 456'):
            self.assertEqual(self.cli.post(URL_LOGIN, {'email': 'lechero@prueba.cl', 'pin': pin}, format='json').status_code, 400, pin)

    def test_M026_bloqueo_por_intentos_fallidos(self):
        codigos = [self.login('LECHERO', '000000').status_code for _ in range(8)]
        self.assertIn(429, codigos)
        self.assertEqual(self.login('LECHERO').status_code, 429)  # ni el PIN correcto entra mientras dura el bloqueo

    def test_M027_refresh_renueva_la_sesion(self):
        tokens = self.login('VETERINARIO').json()['tokens']
        r = self.cli.post(URL_REFRESH, {'refresh': tokens['refresh']}, format='json')
        self.assertEqual(r.status_code, 200)
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION='Bearer ' + r.json()['access'])
        self.assertEqual(c.get(URL_SENSORES).status_code, 200)

    def test_M028_refresh_invalido_401(self):
        self.assertEqual(self.cli.post(URL_REFRESH, {'refresh': 'no.es.un.token'}, format='json').status_code, 401)

    def test_M029_token_manipulado_o_ausente_401(self):
        t = self.login('VETERINARIO').json()['tokens']['access']
        malo = t[:-3] + ('abc' if not t.endswith('abc') else 'xyz')
        for cab in ('Bearer ' + malo, 'Bearer', 'Bearer a b', 'Basic xxx'):
            c = APIClient()
            c.credentials(HTTP_AUTHORIZATION=cab)
            self.assertEqual(c.get(URL_SENSORES).status_code, 401, cab)
        self.assertEqual(APIClient().get(URL_SENSORES).status_code, 401)

    def test_M030_token_de_usuario_desactivado_deja_de_servir(self):
        c = self.cliente('LECHERO')
        self.assertEqual(c.get(URL_SENSORES).status_code, 200)
        Usuario.objects.filter(email='lechero@prueba.cl').update(activo=False)
        self.assertEqual(c.get(URL_SENSORES).status_code, 401)

    def test_M031_refresh_de_usuario_desactivado_401(self):
        tokens = self.login('LECHERO').json()['tokens']
        Usuario.objects.filter(email='lechero@prueba.cl').update(activo=False)
        self.assertEqual(self.cli.post(URL_REFRESH, {'refresh': tokens['refresh']}, format='json').status_code, 401)


# ============================================================ HU-005 / RBAC
class RBACTests(Base):
    def _alta(self, cliente, email='nuevo@prueba.cl', pin='135790', rol=None, **extra):
        return cliente.post(URL_REGISTRO, {'nombre': 'Nuevo', 'email': email, 'pin': pin,
                                           'rol': (rol or self.roles['LECHERO']).id, **extra}, format='json')

    def test_M032_admin_registra_usuario_con_pin_hasheado(self):
        r = self._alta(self.cliente('ADMINISTRADOR'))
        self.assertEqual(r.status_code, 201)
        self.assertNotIn('135790', r.content.decode())
        h = Usuario.objects.get(email='nuevo@prueba.cl').password_hash
        # Durante las pruebas settings.py cambia el algoritmo a MD5 (rapidez); fuera de ellas Django usa PBKDF2.
        self.assertTrue(h.count('$') >= 2, 'el PIN no esta hasheado con sal: ' + h[:12])
        self.assertNotIn('135790', h)

    def test_M033_no_admin_no_registra_usuarios(self):
        for rol in ('VETERINARIO', 'TERNERERO', 'LECHERO'):
            self.assertEqual(self._alta(self.cliente(rol), email=f'{rol}@x.cl').status_code, 403, rol)
        self.assertFalse(Usuario.objects.filter(email__endswith='@x.cl').exists())

    def test_M034_registro_sin_sesion_rechazado_si_ya_hay_usuarios(self):
        self.assertIn(self._alta(APIClient()).status_code, (401, 403))
        self.assertFalse(Usuario.objects.filter(email='nuevo@prueba.cl').exists())

    def test_M035_politica_de_pin_en_registro(self):
        c = self.cliente('ADMINISTRADOR')
        for pin in ('12345', '1234567', 'abcdef', '12 456'):
            self.assertEqual(self._alta(c, email=f'p{len(pin)}{pin[:1]}@x.cl', pin=pin).status_code, 400, pin)

    def test_M036_integridad_email_duplicado_y_rol_inexistente(self):
        c = self.cliente('ADMINISTRADOR')
        self.assertEqual(self._alta(c, email='administrador@prueba.cl').status_code, 400)
        self.assertEqual(c.post(URL_REGISTRO, {'nombre': 'X', 'email': 'y@x.cl', 'pin': '135790', 'rol': 999}, format='json').status_code, 400)

    def test_M037_nombre_con_script_se_guarda_como_texto(self):
        r = self._alta(self.cliente('ADMINISTRADOR'), nombre=XSS)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r['Content-Type'].split(';')[0], 'application/json')
        self.assertEqual(r.json()['usuario']['nombre'], XSS)

    def test_M038_solo_admin_o_veterinario_crean_sensores(self):
        datos = {'ubicacion': 'Corral 9', 'tipo': 'HUMEDAD', 'estado': 'ACTIVO'}
        for rol, esperado in (('ADMINISTRADOR', 201), ('VETERINARIO', 201), ('TERNERERO', 403), ('LECHERO', 403)):
            self.assertEqual(self.cliente(rol).post(URL_SENSORES, datos, format='json').status_code, esperado, rol)

    def test_M039_cualquier_rol_autenticado_puede_listar_sensores(self):
        for rol in ('TERNERERO', 'LECHERO'):
            self.assertEqual(self.cliente(rol).get(URL_SENSORES).status_code, 200, rol)

    def test_M040_solo_admin_gestiona_roles(self):
        for rol in ('VETERINARIO', 'TERNERERO', 'LECHERO'):
            self.assertEqual(self.cliente(rol).post(URL_ROLES, {'nombre': 'NUEVO', 'descripcion': 'x'}, format='json').status_code, 403, rol)
        self.assertEqual(self.cliente('ADMINISTRADOR').post(URL_ROLES, {'nombre': 'NUEVO', 'descripcion': 'x'}, format='json').status_code, 201)

    def test_M041_endpoints_protegidos_rechazan_peticiones_sin_sesion(self):
        c = APIClient()
        for url in ('/api/corrales/', '/api/corrales/1/historial/', URL_SENSORES, URL_ALERTAS, '/api/telemetria/ultima/'):
            self.assertEqual(c.get(url).status_code, 401, url)

    def test_M042_alertas_las_ve_cualquier_rol_autenticado(self):
        with patch.object(self.fb, 'obtener_ultima_lectura', return_value=None):
            for rol in ('TERNERERO', 'LECHERO', 'VETERINARIO'):
                self.assertEqual(self.cliente(rol).get(URL_ALERTAS).status_code, 200, rol)

    def test_M043_permisos_por_rol_en_el_token(self):
        esperado = {'ADMINISTRADOR': (True, True), 'VETERINARIO': (True, True), 'TERNERERO': (False, False), 'LECHERO': (False, True)}
        for rol, (admin, ordenia) in esperado.items():
            p = self.login(rol).json()['permisos']
            self.assertEqual((p['acceso_admin'], p['acceso_ordenia']), (admin, ordenia), rol)


# ======================================================= configuracion segura
class ConfiguracionTests(TestCase):
    def test_M044_debug_desactivado_por_defecto(self):
        self.assertFalse(cfg.DEBUG, 'DEBUG esta activo en la configuracion cargada (.env)')

    def test_M045_secret_key_no_es_la_de_desarrollo(self):
        self.assertFalse(str(cfg.SECRET_KEY).startswith('django-insecure-'),
                         'SECRET_KEY usa el valor por defecto del repositorio')

    def test_M046_allowed_hosts_sin_comodin(self):
        self.assertNotIn('*', cfg.ALLOWED_HOSTS)

    def test_M047_permiso_por_defecto_exige_autenticacion(self):
        permisos = cfg.REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES']
        self.assertIn('rest_framework.permissions.IsAuthenticated', permisos)

    def test_M048_ruta_inexistente_no_expone_rutas(self):
        r = self.client.get('/ruta-que-no-existe/')
        self.assertEqual(r.status_code, 404)
        self.assertNotIn('URLconf', r.content.decode())

