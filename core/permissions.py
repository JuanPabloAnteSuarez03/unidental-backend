from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """
    Permite acceso solo a usuarios del grupo 'Admin'.
    """
    def has_permission(self, request, view):
        return request.user and request.user.groups.filter(name='Admin').exists()


class IsAdminOrUser(BasePermission):
    """
    Permite acceso a usuarios del grupo 'Admin' o 'User'.
    """
    def has_permission(self, request, view):
        return request.user and (
            request.user.groups.filter(name='Admin').exists() or
            request.user.groups.filter(name='User').exists()
        )


class IsAdminOnly(BasePermission):
    """
    Permite acceso SOLO a usuarios del grupo 'Admin'.
    Usuarios 'User' NO pueden acceder.
    """
    def has_permission(self, request, view):
        return request.user and request.user.groups.filter(name='Admin').exists()


class IsUserOnly(BasePermission):
    """
    Permite acceso SOLO a usuarios del grupo 'User'.
    Usuarios 'Admin' NO pueden acceder.
    """
    def has_permission(self, request, view):
        return request.user and request.user.groups.filter(name='User').exists()


class IsAuthenticated(BasePermission):
    """
    Permite acceso a cualquier usuario autenticado (Admin o User).
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated 