from rest_framework.permissions import BasePermission

from .models import Role, Status


class IsAdmin(BasePermission):
    """Rôle ADMIN."""

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role == Role.ADMIN
        )


class IsApprovedSaei(BasePermission):
    """Rôle SAEI et statut APPROVED (permet de se connecter / d'accéder aux ressources SAEI)."""

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role == Role.SAEI
            and request.user.status == Status.APPROVED
        )


class IsEntrepreneur(BasePermission):
    """Rôle ENTREPRENEUR."""

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role == Role.ENTREPRENEUR
        )
