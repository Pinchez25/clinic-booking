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
    availability_slots = serializers.ListField(child=serializers.DateTimeField())
