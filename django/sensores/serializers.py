from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from .models import Alerta, LecturaSensor, Rol, Sensor, Usuario


class RolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rol
        fields = ['id', 'nombre', 'descripcion']


class UsuarioSerializer(serializers.ModelSerializer):
    rol_nombre = serializers.CharField(source='rol.nombre', read_only=True)

    class Meta:
        model = Usuario
        fields = ['id', 'nombre', 'email', 'rol', 'rol_nombre', 'activo']


class RegistroUsuarioPINSerializer(serializers.ModelSerializer):
    pin = serializers.CharField(write_only=True, min_length=6, max_length=6)

    class Meta:
        model = Usuario
        fields = ['id', 'nombre', 'email', 'rol', 'pin', 'activo']

    def validate_email(self, value):
        return value.strip().lower()

    def validate_pin(self, value):
        """Valida que el PIN esté compuesto exclusivamente por 6 dígitos numéricos."""
        if not value.isdigit() or len(value) != 6:
            raise serializers.ValidationError("El PIN debe contener únicamente 6 números.")
        return value

    def create(self, validated_data):
        pin = validated_data.pop('pin')
        validated_data['password_hash'] = make_password(pin)
        return super().create(validated_data)


class LoginPINSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    pin = serializers.CharField(required=True, min_length=6, max_length=6, write_only=True)

    def validate_email(self, value):
        return value.strip().lower()

    def validate_pin(self, value):
        if not value.isdigit() or len(value) != 6:
            raise serializers.ValidationError("El PIN debe ser un código numérico de 6 dígitos.")
        return value


class SensorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sensor
        fields = ['id', 'ubicacion', 'tipo', 'estado']


class LecturaSensorSerializer(serializers.ModelSerializer):
    sensor_ubicacion = serializers.CharField(source='sensor.ubicacion', read_only=True)
    sensor_tipo = serializers.CharField(source='sensor.tipo', read_only=True)

    class Meta:
        model = LecturaSensor
        fields = ['id', 'sensor', 'sensor_ubicacion', 'sensor_tipo', 'valor', 'unidad', 'fecha_hora']


class AlertaSerializer(serializers.ModelSerializer):
    sensor_ubicacion = serializers.CharField(source='sensor.ubicacion', read_only=True)

    class Meta:
        model = Alerta
        fields = [
            'id',
            'sensor',
            'sensor_ubicacion',
            'lectura_sensor',
            'tipo_alerta',
            'nivel',
            'fecha_hora',
            'mensaje',
            'estado_lectura',
        ]
        read_only_fields = ['id', 'sensor', 'lectura_sensor', 'tipo_alerta', 'nivel', 'fecha_hora', 'mensaje']

    def validate_estado_lectura(self, value):
        val = value.strip().upper()
        if val not in ['PENDIENTE', 'LEIDA', 'RESUELTA']:
            raise serializers.ValidationError("El estado_lectura debe ser PENDIENTE, LEIDA o RESUELTA.")
        return val


class TelemetriaFirebaseInputSerializer(serializers.Serializer):
    dispositivo = serializers.CharField(max_length=64, required=False, default='ESP8266_Sensor1')
    corral_id = serializers.IntegerField(min_value=1, max_value=100, required=False, default=1)
    temperatura_celsius = serializers.FloatField(min_value=-20.0, max_value=45.0, required=True)
    humedad_ambiente_pct = serializers.FloatField(min_value=0.0, max_value=100.0, required=True)


class RefreshTokenPINSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=True)


class IngestaIoTInputSerializer(serializers.Serializer):
    sensor_id = serializers.IntegerField(required=True)
    valor = serializers.FloatField(required=True)
    unidad = serializers.CharField(required=True, max_length=20)
    dispositivo = serializers.CharField(required=False, max_length=64, default='Sensor_1')
    corral_id = serializers.IntegerField(required=False, min_value=1, max_value=100, default=1)


class VerificacionRFIDInputSerializer(serializers.Serializer):
    codigo_rfid = serializers.CharField(required=True, max_length=64)
    bajada = serializers.IntegerField(required=False, min_value=1, max_value=38)
