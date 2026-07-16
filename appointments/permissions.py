from django.contrib.auth import get_user_model
from rest_framework.permissions import BasePermission

User = get_user_model()


class IsAppointmentOwner(BasePermission):
    """Allows access only to the patient who owns the appointment."""

    message = "You do not have permission to modify this appointment."

    def has_object_permission(self, request, view, obj):
        return obj.patient == request.user


class CanManageAppointment(BasePermission):
    def has_object_permission(self, request, view, obj):
        user = request.user

        if user.has_role(User.Role.ADMIN):
            return True

        if user.has_role(User.Role.DOCTOR):
            return obj.doctor.user_id == user.id

        return obj.patient_id == user.id
