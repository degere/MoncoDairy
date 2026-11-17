"""
Prueba de humo contra la API levantada con `python manage.py runserver` (Eva-3).
Archivo NUEVO. Uso:
    python smoke_api_live.py http://127.0.0.1:8765
Requiere datos semilla (ver seed_eva3.py). Imprime una linea por caso:
    ID | metodo ruta | esperado | obtenido | OK/DISCREPANCIA | detalle
"""
import json
import sys
import threading
import time
import urllib.error
import urllib.request

BASE = sys.argv[1].rstrip('/') if len(sys.argv) > 1 else 'http://127.0.0.1:8765'
RFID = '/api/orde%C3%B1a/rfid/'
resultados = []


def req(method, path, body=None, raw=None, headers=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    h = {'Content-Type': 'application/json'}
    h.update(headers or {})
    r = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            txt = resp.read().decode('utf-8', 'replace')
            code = resp.status
    except urllib.error.HTTPError as e:
        txt = e.read().decode('utf-8', 'replace')
        code = e.code
    return code, txt, (time.perf_counter() - t0) * 1000


def caso(cid, method, path, esperado, body=None, raw=None, check=None, nota=''):
    code, txt, ms = req(method, path, body, raw)
    ok = code in esperado if isinstance(esperado, tuple) else code == esperado
    extra = ''
    if check:
        ok2, extra = check(code, txt)
        ok = ok and ok2
    resultados.append((cid, f'{method} {path}', esperado, code, 'OK' if ok else 'DISCREPANCIA',
                       (nota + ' ' + extra).strip(), round(ms, 1)))
    return code, txt


def contiene(*frag):
    def f(code, txt):
        faltan = [x for x in frag if x not in txt]
        return (not faltan, 'faltan: %s' % faltan if faltan else '')
    return f


def no_contiene(*frag):
    def f(code, txt):
        hay = [x for x in frag if x in txt]
        return (not hay, 'expone: %s' % hay if hay else '')
    return f


S_T, S_H = 1, 2  # ids creados por seed_eva3.py

caso('L01', 'POST', '/api/iot/ingesta/', 201, {'sensor_id': S_T, 'valor': 18.5, 'unidad': '°C'}, nota='lectura normal')
caso('L02', 'POST', '/api/iot/ingesta/', 400, {'sensor_id': S_T, 'valor': 80, 'unidad': '°C'}, nota='fuera de rango fisico')
caso('L03', 'POST', '/api/iot/ingesta/', 400, raw=b'{"sensor_id": 1, "valor": ', nota='JSON malformado',
     check=no_contiene('Traceback', 'File "'))
caso('L04', 'POST', '/api/iot/ingesta/', 404, {'sensor_id': "' OR '1'='1", 'valor': 18, 'unidad': '°C'}, nota='SQLi en sensor_id')
caso('L05', 'POST', '/api/iot/ingesta/', 400, {'sensor_id': S_T, 'valor': 18, 'unidad': "<script>alert('hack')</script>"},
     nota='XSS en unidad')
caso('L06', 'POST', '/api/iot/ingesta/', (401, 403), {'sensor_id': S_H, 'valor': 50, 'unidad': '%'}, nota='sin credenciales')
caso('L07', 'GET', '/api/iot/ingesta/', 405, nota='metodo no permitido')
caso('L08', 'POST', RFID, 200, {'codigo_rfid': 'RFID-0001', 'bajada': 4},
     check=contiene('"bloquear_ordenia":true'), nota='vaca con tratamiento activo')
caso('L09', 'POST', RFID, 200, {'codigo_rfid': 'RFID-0002', 'bajada': 4},
     check=contiene('"bloquear_ordenia":false'), nota='vaca sana')
caso('L10', 'POST', RFID, 404, {'codigo_rfid': 'RFID-9999'}, nota='RFID inexistente')
caso('L11', 'POST', RFID, 200, {'codigo_rfid': 'RFID-0003', 'bajada': 4},
     check=contiene('"bloquear_ordenia":true'), nota='resguardo vigente (fecha_fin futura)')
caso('L12', 'POST', '/api/auth/login-pin/', 200, {'email': 'ana@moncopulli.cl', 'pin': '482913'},
     check=no_contiene('password_hash', '482913'), nota='login correcto')
caso('L13', 'POST', '/api/auth/login-pin/', 401, {'email': 'ana@moncopulli.cl', 'pin': '000000'}, nota='PIN incorrecto')
caso('L14', 'POST', '/api/auth/login-pin/', 400, {'email': "' OR '1'='1", 'pin': '000000'}, nota='SQLi en email')
for i in range(8):
    req('POST', '/api/auth/login-pin/', {'email': 'ana@moncopulli.cl', 'pin': '11111%d' % i})
caso('L15', 'POST', '/api/auth/login-pin/', (403, 423, 429), {'email': 'ana@moncopulli.cl', 'pin': '482913'},
     nota='login correcto tras 9 PIN incorrectos seguidos (fuerza bruta)')
caso('L16', 'POST', '/api/auth/registro-pin/', (401, 403),
     {'nombre': 'Intruso', 'email': 'intruso@x.cl', 'rol': 2, 'pin': '000000', 'activo': True},
     nota='alta de ADMINISTRADOR sin autenticacion')
caso('L17', 'GET', '/ruta-que-no-existe/', 404, check=no_contiene('URLconf', 'api/iot/ingesta'),
     nota='pagina 404 no debe revelar rutas (DEBUG)')
caso('L18', 'GET', '/admin/', (200, 302), nota='panel admin expuesto')

# Concurrencia: 10 hilos x 20 lecturas contra SQLite
errores, codigos = [], []
lock = threading.Lock()


def worker(n):
    for i in range(20):
        try:
            c, _, _ = req('POST', '/api/iot/ingesta/', {'sensor_id': S_T, 'valor': 15 + (i % 5), 'unidad': '°C'})
        except Exception as e:  # noqa: BLE001
            c = 'EXC:' + type(e).__name__
        with lock:
            codigos.append(c)


t0 = time.perf_counter()
hilos = [threading.Thread(target=worker, args=(k,)) for k in range(10)]
[h.start() for h in hilos]
[h.join() for h in hilos]
dt = time.perf_counter() - t0
n201 = codigos.count(201)
resultados.append(('L19', 'POST /api/iot/ingesta/ x200 (10 hilos)', '200x201', f'{n201}x201 / otros={len(codigos) - n201}',
                   'OK' if n201 == 200 else 'DISCREPANCIA',
                   f'{dt:.2f} s total; codigos distintos de 201: {sorted(set(map(str, codigos)) - {"201"})}', round(dt * 1000, 1)))

print('ID | peticion | esperado | obtenido | estado | detalle | ms')
for r in resultados:
    print(' | '.join(map(str, r)))
print('TOTAL', len(resultados), 'OK', sum(r[4] == 'OK' for r in resultados),
      'DISCREPANCIA', sum(r[4] != 'OK' for r in resultados))
