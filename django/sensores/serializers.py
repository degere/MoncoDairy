from rest_framework import serializers
from django.contrib.auth.hashers import make_password, check_password
from .models import Usuario, Rol

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

    def validate_pin(self, value):
        """Valida que el PIN esté compuesto exclusivamente por 6 dígitos numéricos."""
        if not value.isdigit():
            raise serializers.ValidationError("El PIN debe contener únicamente 6 números.")
        return value

    def create(self, validated_data):
        pin = validated_data.pop('pin')
        # Se hashea el PIN de 6 dígitos antes de guardarlo en la columna password_hash
        validated_data['password_hash'] = make_password(pin)
        return super().create(validated_data)


class LoginPINSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    pin = serializers.CharField(required=True, min_length=6, max_length=6)

    def validate_pin(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("El PIN debe ser un código numérico de 6 dígitos.")
        return value