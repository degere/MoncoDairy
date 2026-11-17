from django.db import models


class Rol(models.Model):
    nombre = models.CharField(unique=True, max_length=50)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'rol'

    def __str__(self):
        return self.nombre


class Usuario(models.Model):
    rol = models.ForeignKey(Rol, models.DO_NOTHING)
    nombre = models.CharField(max_length=100)
    email = models.CharField(unique=True, max_length=150)
    password_hash = models.CharField(max_length=255)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'usuario'

    def __str__(self):
        return f"{self.nombre} ({self.email})"


class RegistroOffline(models.Model):
    id = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey(Usuario, models.DO_NOTHING)
    fecha_creacion = models.DateTimeField()
    sincronizado = models.BooleanField(default=False)

    class Meta:
        db_table = 'registro_offline'


class EventoSanitario(models.Model):
    id = models.BigAutoField(primary_key=True)
    registro_offline = models.ForeignKey(RegistroOffline, models.SET_NULL, blank=True, null=True)
    fecha_hora = models.DateTimeField()
    descripcion = models.TextField()
    gravedad = models.CharField(max_length=20)

    class Meta:
        db_table = 'evento_sanitario'


class CollarRfid(models.Model):
    codigo = models.CharField(unique=True, max_length=64)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'collar_rfid'


class Animal(models.Model):
    id = models.BigAutoField(primary_key=True)
    evento_sanitario = models.ForeignKey(EventoSanitario, models.SET_NULL, blank=True, null=True)
    collar_rfid = models.OneToOneField(CollarRfid, models.SET_NULL, blank=True, null=True)
    fecha_nacimiento = models.DateField()
    estado = models.CharField(max_length=30)

    class Meta:
        db_table = 'animal'


class Sensor(models.Model):
    ubicacion = models.CharField(max_length=100)
    tipo = models.CharField(max_length=50)
    estado = models.CharField(max_length=30, default='ACTIVO')

    class Meta:
        db_table = 'sensor'

    def __str__(self):
        return f"{self.tipo} - {self.ubicacion}"


class LecturaSensor(models.Model):
    id = models.BigAutoField(primary_key=True)
    sensor = models.ForeignKey(Sensor, models.CASCADE)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    unidad = models.CharField(max_length=20)
    fecha_hora = models.DateTimeField()

    class Meta:
        db_table = 'lectura_sensor'


class Alerta(models.Model):
    id = models.BigAutoField(primary_key=True)
    sensor = models.ForeignKey(Sensor, models.CASCADE)
    lectura_sensor = models.ForeignKey(LecturaSensor, models.SET_NULL, blank=True, null=True)
    tipo_alerta = models.CharField(max_length=50)
    nivel = models.CharField(max_length=20)
    fecha_hora = models.DateTimeField()
    mensaje = models.TextField()
    estado_lectura = models.CharField(max_length=30, default='PENDIENTE')

    class Meta:
        db_table = 'alerta'


class Tratamiento(models.Model):
    id = models.BigAutoField(primary_key=True)
    evento_sanitario = models.ForeignKey(EventoSanitario, models.CASCADE)
    medicamento = models.CharField(max_length=100)
    dosis = models.CharField(max_length=50)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(blank=True, null=True)
    bloqueo_leche = models.BooleanField(default=False)

    class Meta:
        db_table = 'tratamiento'
