from rest_framework.permissions import BasePermission

from .models import User


class HasRole(BasePermission):
    required_role = None

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.has_role(self.required_role)


class IsPatient(HasRole):
    message = "Only patients can perform this action."
    required_role = User.Role.PATIENT


class IsDoctor(HasRole):
    message = "Only doctors can perform this action."
    required_role = User.Role.DOCTOR


class IsAdmin(HasRole):
    message = "Only admins can perform this action."
    required_role = User.Role.ADMIN
