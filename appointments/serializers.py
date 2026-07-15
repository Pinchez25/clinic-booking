from rest_framework import serializers

from accounts.serializers import UserSerializer
from appointments.models import Appointment
from doctors.serializers import DoctorSerializer


class AppointmentSerializer(serializers.ModelSerializer):
    doctor = DoctorSerializer(read_only=True)
    patient = UserSerializer(read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "doctor",
            "patient",
            "slot_time",
            "status",
            "cancel_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class BookAppointmentSerializer(serializers.Serializer):
    """Validates request shape only. Business rules live in services."""

    doctor_id = serializers.UUIDField()
    slot_time = serializers.DateTimeField()


class CancelAppointmentSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=1, max_length=500)


class RescheduleAppointmentSerializer(serializers.Serializer):
    """Validates request shape only. Business rules live in services."""

    slot_time = serializers.DateTimeField()
