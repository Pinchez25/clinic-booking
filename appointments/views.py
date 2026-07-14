import logging

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.mixins import CreateModelMixin, RetrieveModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from accounts.permissions import IsPatient
from doctors.models import Doctor

from .models import Appointment
from .permissions import IsAppointmentOwner
from .serializers import (
    AppointmentSerializer,
    BookAppointmentSerializer,
    CancelAppointmentSerializer,
    RescheduleAppointmentSerializer,
)
from .utils import AppointmentError, book_appointment, cancel_appointment, reschedule_appointment

logger = logging.getLogger("appointments")


class AppointmentViewSet(CreateModelMixin, RetrieveModelMixin, GenericViewSet):
    serializer_class = AppointmentSerializer
    permission_classes = [IsAuthenticated, IsPatient]

    def get_queryset(self):
        return Appointment.objects.select_related("doctor__user", "patient").filter(
            patient=self.request.user
        )

    def get_permissions(self):
        if self.action in ("cancel", "reschedule"):
            return [IsAuthenticated(), IsPatient(), IsAppointmentOwner()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = BookAppointmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            doctor = Doctor.objects.select_related("user").get(
                pk=serializer.validated_data["doctor_id"],
                is_available=True,
            )
        except Doctor.DoesNotExist:
            raise NotFound("Doctor not found or not available.") from None

        try:
            appointment = book_appointment(
                doctor=doctor,
                patient=request.user,
                slot_time=serializer.validated_data["slot_time"],
            )
        except AppointmentError as e:
            raise ValidationError({"detail": str(e)}) from e

        return Response(AppointmentSerializer(appointment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], url_path="cancel")
    def cancel(self, request, pk=None):
        appointment = self.get_object()
        serializer = CancelAppointmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            appointment = cancel_appointment(
                appointment=appointment,
                reason=serializer.validated_data["reason"],
            )
        except AppointmentError as e:
            raise ValidationError({"detail": str(e)}) from e

        return Response(AppointmentSerializer(appointment).data)

    @action(detail=True, methods=["patch"], url_path="reschedule")
    def reschedule(self, request, pk=None):
        appointment = self.get_object()
        serializer = RescheduleAppointmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            appointment = reschedule_appointment(
                appointment=appointment,
                new_slot_time=serializer.validated_data["slot_time"],
            )
        except AppointmentError as e:
            raise ValidationError({"detail": str(e)}) from e
        return Response(AppointmentSerializer(appointment).data)


class PatientViewSet(RetrieveModelMixin, GenericViewSet):
    permission_classes = [IsAuthenticated, IsPatient]
    queryset = get_user_model().objects.all()

    def get_object(self):
        user_id = self.kwargs["pk"]
        if str(self.request.user.id) != str(user_id):
            raise PermissionDenied("You can only view your own appointments.")
        return self.request.user

    @action(detail=True, methods=["get"])
    def appointments(self, request, pk=None):
        patient = self.get_object()
        appointments = (
            Appointment.objects.select_related("doctor__user", "patient")
            .filter(patient=patient, status=Appointment.Status.ACTIVE)
            .order_by("slot_time")
        )
        return Response(AppointmentSerializer(appointments, many=True).data)
