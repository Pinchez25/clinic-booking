from rest_framework.permissions import BasePermission


class IsAppointmentOwner(BasePermission):
    """Allows access only to the patient who owns the appointment."""

    message = "You do not have permission to modify this appointment."

    def has_object_permission(self, request, view, obj):
        return obj.patient == request.user
