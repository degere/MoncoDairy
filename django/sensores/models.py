# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class Alerta(models.Model):
    id = models.BigAutoField(primary_key=True)
    sensor = models.ForeignKey('Sensor', models.DB_CASCADE)
    lectura_sensor = models.ForeignKey('LecturaSensor', models.DB_SET_NULL, blank=True, null=True)
    tipo_alerta = models.CharField(max_length=50)
    nivel = models.CharField(max_length=20)
    fecha_hora = models.DateTimeField()
    mensaje = models.TextField()
    estado_lectura = models.CharField(max_length=30)

    class Meta:
        managed = False
        db_table = 'alerta'


class Animal(models.Model):
    id = models.BigAutoField(primary_key=True)
    evento_sanitario = models.ForeignKey('EventoSanitario', models.DB_SET_NULL, blank=True, null=True)
    collar_rfid = models.OneToOneField('CollarRfid', models.DB_SET_NULL, blank=True, null=True)
    fecha_nacimiento = models.DateField()
    estado = models.CharField(max_length=30)

    class Meta:
        managed = False
        db_table = 'animal'


class CollarRfid(models.Model):
    codigo = models.CharField(unique=True, max_length=64)
    activo = models.BooleanField()

    class Meta:
        managed = False
        db_table = 'collar_rfid'


class EventoSanitario(models.Model):
    id = models.BigAutoField(primary_key=True)
    registro_offline = models.ForeignKey('RegistroOffline', models.DB_SET_NULL, blank=True, null=True)
    fecha_hora = models.DateTimeField()
    descripcion = models.TextField()
    gravedad = models.CharField(max_length=20)

    class Meta:
        managed = False
        db_table = 'evento_sanitario'


class LecturaSensor(models.Model):
    id = models.BigAutoField(primary_key=True)
    sensor = models.ForeignKey('Sensor', models.DB_CASCADE)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    unidad = models.CharField(max_length=20)
    fecha_hora = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'lectura_sensor'


class RegistroOffline(models.Model):
    id = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey('Usuario', models.DO_NOTHING)
    fecha_creacion = models.DateTimeField()
    sincronizado = models.BooleanField()

    class Meta:
        managed = False
        db_table = 'registro_offline'


class Rol(models.Model):
    nombre = models.CharField(unique=True, max_length=50)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'rol'


class Sensor(models.Model):
    ubicacion = models.CharField(max_length=100)
    tipo = models.CharField(max_length=50)
    estado = models.CharField(max_length=30)

    class Meta:
        managed = False
        db_table = 'sensor'


class Tratamiento(models.Model):
    id = models.BigAutoField(primary_key=True)
    evento_sanitario = models.ForeignKey(EventoSanitario, models.DB_CASCADE)
    medicamento = models.CharField(max_length=100)
    dosis = models.CharField(max_length=50)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(blank=True, null=True)
    bloqueo_leche = models.BooleanField()

    class Meta:
        managed = False
        db_table = 'tratamiento'


class Usuario(models.Model):
    rol = models.ForeignKey(Rol, models.DO_NOTHING)
    nombre = models.CharField(max_length=100)
    email = models.CharField(unique=True, max_length=150)
    password_hash = models.CharField(max_length=255)
    activo = models.BooleanField()

    class Meta:
        managed = False
        db_table = 'usuario'
