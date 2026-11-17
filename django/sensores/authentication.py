"""
Autenticación JWT personalizada para el modelo operativo `Usuario` (PIN de 6 dígitos)
con soporte para RBAC según el organigrama de MoncoDairy.
"""

from datetime import datetime, timezone as dt_timezone
from django.conf import settings
from rest_framework import authentication, exceptions
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
import jwt
from .models import Usuario


def construir_permisos_rol(rol_nombre: str) -> dict:
    rol = (rol_nombre or '').upper()
    return {
        "rol": rol,
        "acceso_admin": rol in ["ADMINISTRADOR", "VETERINARIO"],
        "acceso_terreno": True,
        "acceso_maternidad": rol in ["ADMINISTRADOR", "PARTERO", "TERNERERO", "VETERINARIO"],
        "acceso_ordenia": rol in ["ADMINISTRADOR", "LECHERO", "VETERINARIO"],
    }


def generar_tokens_para_usuario(usuario: Usuario) -> dict:
    """
    Genera un par de tokens JWT (access y refresh) firmados con SECRET_KEY
    incluyendo los claims de identidad y rol del usuario operativo.
    """
    rol_nombre = usuario.rol.nombre.upper() if usuario.rol else "OPERADOR"
    permisos = construir_permisos_rol(rol_nombre)

    refresh = RefreshToken()
    refresh['user_id'] = usuario.id
    refresh['usuario_id'] = usuario.id
    refresh['email'] = usuario.email
    refresh['nombre'] = usuario.nombre
    refresh['rol'] = rol_nombre
    refresh['permisos'] = permisos

    access = refresh.access_token
    access['user_id'] = usuario.id
    access['usuario_id'] = usuario.id
    access['email'] = usuario.email
    access['nombre'] = usuario.nombre
    access['rol'] = rol_nombre
    access['permisos'] = permisos

    return {
        'access': str(access),
        'refresh': str(refresh),
    }


class UsuarioAutenticadoWrapper:
    """
    Adaptador compatible con `request.user` de Django REST Framework
    para instancias del modelo `sensores.models.Usuario`.
    """

    def __init__(self, usuario: Usuario):
        self.usuario = usuario
        self.id = usuario.id
        self.pk = usuario.id
        self.email = usuario.email
        self.nombre = usuario.nombre
        self.activo = usuario.activo
        self.rol = usuario.rol
        self.rol_nombre = usuario.rol.nombre.upper() if usuario.rol else "OPERADOR"
        self.permisos = construir_permisos_rol(self.rol_nombre)
        self.is_active = bool(usuario.activo)
        self.is_staff = self.rol_nombre in ["ADMINISTRADOR", "VETERINARIO"]
        self.is_superuser = self.rol_nombre == "ADMINISTRADOR"

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    def __str__(self) -> str:
        return f"{self.nombre} ({self.email})"


class UsuarioPINJWTAuthentication(authentication.BaseAuthentication):
    """
    Autentica peticiones HTTP mediante el encabezado `Authorization: Bearer <token>`
    validando la firma criptográfica y resolviendo el usuario en la tabla `usuario`.
    """

    keyword = 'Bearer'

    def authenticate(self, request):
        auth_header = authentication.get_authorization_header(request).split()
        if not auth_header or auth_header[0].lower() != self.keyword.lower().encode():
            return None

        if len(auth_header) == 1:
            raise exceptions.AuthenticationFailed('Encabezado Authorization inválido: falta el token.')
        if len(auth_header) > 2:
            raise exceptions.AuthenticationFailed('Encabezado Authorization inválido: contiene espacios extra.')

        raw_token = auth_header[1].decode('utf-8')

        try:
            validated_token = AccessToken(raw_token)
        except Exception as exc:
            raise exceptions.AuthenticationFailed('Token JWT inválido o expirado.') from exc

        usuario_id = validated_token.get('usuario_id') or validated_token.get('user_id')
        email = validated_token.get('email')

        if not usuario_id:
            return None

        try:
            filtros = {'id': usuario_id, 'activo': True}
            if email:
                filtros['email'] = email
            usuario = Usuario.objects.select_related('rol').get(**filtros)
        except Usuario.DoesNotExist:
            # Si el token pertenece a un superusuario de django.contrib.auth, delegar a JWTAuthentication estándar
            return None

        return (UsuarioAutenticadoWrapper(usuario), validated_token)

    def authenticate_header(self, request):
        return self.keyword


try:
    from drf_spectacular.extensions import OpenApiAuthenticationExtension

    class UsuarioPINJWTAuthenticationScheme(OpenApiAuthenticationExtension):
        target_class = 'sensores.authentication.UsuarioPINJWTAuthentication'
        name = 'pinJwtAuth'

        def get_security_definition(self, auto_schema):
            return {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
            }
except ImportError:
    pass
