from datetime import date

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from .models import Doctor
from .serializers import DoctorAvailabilitySerializer, DoctorSerializer
from .utils import get_available_slots


class DoctorViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    serializer_class = DoctorSerializer
    queryset = Doctor.objects.filter(is_available=True).select_related("user")
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=["get"], url_path="availability")
    def doctor_availability(self, request, pk=None):
        doctor = self.get_object()

        raw_date = request.query_params.get("date")

        if not raw_date:
            return Response(
                {"detail": "Date query parameter is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            target_date = date.fromisoformat(raw_date)
        except ValueError:
            return Response(
                {"detail": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        available_slots = get_available_slots(doctor, target_date)

        serializer = DoctorAvailabilitySerializer(
            {"doctor": doctor, "date": target_date, "available_slots": available_slots}
        )
        return Response(serializer.data)
