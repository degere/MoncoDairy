"""
Datos semilla para la prueba en vivo (archivo NUEVO). Ejecutar sobre una base
de datos de prueba (nunca sobre la del equipo):
    python manage.py shell < seed_eva3.py
"""
import datetime
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from sensores.models import Rol, Usuario, Sensor, CollarRfid, Animal, EventoSanitario, Tratamiento

hoy = datetime.date.today()
lechero = Rol.objects.create(nombre='LECHERO')          # id 1
Rol.objects.create(nombre='ADMINISTRADOR')              # id 2
Usuario.objects.create(rol=lechero, nombre='Ana', email='ana@moncopulli.cl',
                       password_hash=make_password('482913'), activo=True)
Sensor.objects.create(ubicacion='Sala de partos', tipo='TEMPERATURA', estado='ACTIVO')   # id 1
Sensor.objects.create(ubicacion='Ternerera 1', tipo='HUMEDAD', estado='ACTIVO')          # id 2


def vaca(codigo, fecha_fin=..., bloqueo=True):
    c = CollarRfid.objects.create(codigo=codigo, activo=True)
    ev = None
    if fecha_fin is not ...:
        ev = EventoSanitario.objects.create(fecha_hora=timezone.now(), descripcion='Mastitis', gravedad='ALTA')
        Tratamiento.objects.create(evento_sanitario=ev, medicamento='Cefalexina', dosis='10 ml',
                                   fecha_inicio=hoy - datetime.timedelta(days=2), fecha_fin=fecha_fin,
                                   bloqueo_leche=bloqueo)
    Animal.objects.create(collar_rfid=c, evento_sanitario=ev, fecha_nacimiento=datetime.date(2021, 1, 1),
                          estado='ORDENA')


vaca('RFID-0001', fecha_fin=None)                                   # tratamiento activo
vaca('RFID-0002')                                                   # sana
vaca('RFID-0003', fecha_fin=hoy + datetime.timedelta(days=3))       # periodo de resguardo vigente
print('semilla OK')
