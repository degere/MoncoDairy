"""
Permisos basados en roles (RBAC) para los endpoints de MoncoDairy.
"""

from rest_framework import permissions


class EsAdministradorOVeterinario(permissions.BasePermission):
    """
    Permite el acceso exclusivamente a usuarios con rol ADMINISTRADOR o VETERINARIO,
    o superusuarios de Django.
    """
    message = "Se requieren permisos de Administrador o Veterinario para realizar esta acción."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if getattr(user, 'is_superuser', False) or getattr(user, 'is_staff', False):
            return True
        rol = getattr(user, 'rol_nombre', '').upper()
        return rol in ['ADMINISTRADOR', 'VETERINARIO']


class PermisoRegistroUsuario(permissions.BasePermission):
    """
    Exige rol ADMINISTRADOR para registrar nuevos usuarios, salvo durante el
    bootstrapping inicial cuando aún no existen usuarios en la base de datos.
    """
    message = "Solo un Administrador autenticado puede registrar nuevos usuarios."

    def has_permission(self, request, view):
        from .models import Usuario
        user = request.user
        if user and user.is_authenticated:
            if getattr(user, 'is_superuser', False):
                return True
            if getattr(user, 'rol_nombre', '').upper() == 'ADMINISTRADOR':
                return True
        # Permitir bootstrapping únicamente si no hay ningún usuario registrado aún
        return not Usuario.objects.exists()
