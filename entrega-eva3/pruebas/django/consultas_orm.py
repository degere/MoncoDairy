"""
Inspeccion del esquema real y de las consultas ORM criticas (archivo NUEVO, Eva-3).
Ejecutar sobre una base de prueba ya migrada y con seed_eva3.py cargado:
    python manage.py shell -c "exec(open('consultas_orm.py', encoding='utf-8').read())"
"""
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

print('== Indices por tabla (SQLite PRAGMA index_list) ==')
with connection.cursor() as c:
    for t in ['alerta', 'animal', 'collar_rfid', 'evento_sanitario', 'lectura_sensor', 'registro_offline',
              'rol', 'sensor', 'tratamiento', 'usuario']:
        c.execute(f'PRAGMA index_list("{t}")')
        idx = []
        for row in c.fetchall():
            c.execute(f'PRAGMA index_info("{row[1]}")')
            cols = [r[2] for r in c.fetchall()]
            idx.append(f"{'UNIQUE ' if row[2] else ''}({', '.join(cols)})")
        print(f'{t}: {"; ".join(idx) or "(solo PK)"}')
    c.execute('PRAGMA foreign_keys')
    print('PRAGMA foreign_keys =', c.fetchone()[0])

cli = APIClient()
casos = [
    ('RFID tratamiento activo', '/api/ordeña/rfid/', {'codigo_rfid': 'RFID-0001', 'bajada': 4}),
    ('RFID vaca sana', '/api/ordeña/rfid/', {'codigo_rfid': 'RFID-0002', 'bajada': 4}),
    ('Ingesta con alerta (9 C)', '/api/iot/ingesta/', {'sensor_id': 1, 'valor': 9, 'unidad': '°C'}),
    ('Login PIN', '/api/auth/login-pin/', {'email': 'ana@moncopulli.cl', 'pin': '482913'}),
]
print('\n== Consultas SQL por peticion ==')
for nombre, url, body in casos:
    with CaptureQueriesContext(connection) as ctx:
        r = cli.post(url, body, format='json', SERVER_NAME='localhost')
    print(f'{nombre}: HTTP {r.status_code}, {len(ctx.captured_queries)} consultas')
    for q in ctx.captured_queries:
        print('   ', q['sql'][:160])
