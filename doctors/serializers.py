from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from .models import Doctor


class DoctorSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Doctor
        fields = ["id", "full_name", "email", "work_start", "work_end", "is_available"]

    @staticmethod
    def get_full_name(obj) -> str:
        return obj.user.get_full_name() or obj.user.email


class DoctorAvailabilitySerializer(serializers.Serializer):
    doctor = DoctorSerializer()
    date = serializers.DateField()
    available_slots = serializers.ListField(child=serializers.DateTimeField())


class AvailabilityQuerySerializer(serializers.Serializer):
    date = serializers.DateField()

    def validate_date(self, value):
        today = timezone.localdate()
        latest = today + timedelta(days=settings.MAX_BOOKING_DAYS_AHEAD)

        if value < today:
            raise serializers.ValidationError("Appointments cannot be booked in the past.")

        if value > latest:
            raise serializers.ValidationError(
                f"Appointments can only be booked up to "
                f"{settings.MAX_BOOKING_DAYS_AHEAD} days in advance."
            )

        return value
