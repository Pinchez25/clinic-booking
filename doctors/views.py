from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from .models import Doctor
from .serializers import (
    AvailabilityQuerySerializer,
    DoctorAvailabilitySerializer,
    DoctorSerializer,
)
from .utils import get_available_slots


class DoctorViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    queryset = Doctor.objects.select_related("user")
    serializer_class = DoctorSerializer
    permission_classes = [IsAuthenticated]

    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["is_available"]

    @action(detail=True, methods=["get"], url_path="availability")
    def doctor_availability(self, request, pk=None):
        doctor = self.get_object()

        query_serializer = AvailabilityQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)

        target_date = query_serializer.validated_data["date"]

        available_slots = get_available_slots(
            doctor=doctor,
            target_date=target_date,
        )

        serializer = DoctorAvailabilitySerializer(
            {
                "doctor": doctor,
                "date": target_date,
                "available_slots": available_slots,
            }
        )

        return Response(serializer.data, status=status.HTTP_200_OK)
