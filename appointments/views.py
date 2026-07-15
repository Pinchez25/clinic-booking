import logging

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
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
from .utils import (
    AppointmentError,
    book_appointment,
    cancel_appointment,
    reschedule_appointment,
)

logger = logging.getLogger("appointments")


class AppointmentViewSet(CreateModelMixin, RetrieveModelMixin, GenericViewSet):
    serializer_class = AppointmentSerializer
    permission_classes = [IsAuthenticated, IsPatient]

    def get_queryset(self):
        qs = Appointment.objects.select_related("doctor__user", "patient").order_by("slot_time")
        if self.action in {"cancel", "reschedule"}:
            return qs
        return qs.filter(patient=self.request.user)

    def get_permissions(self):
        if self.action in {"cancel", "reschedule"}:
            return [
                IsAuthenticated(),
                IsPatient(),
                IsAppointmentOwner(),
            ]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = BookAppointmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        doctor = get_object_or_404(
            Doctor,
            pk=serializer.validated_data["doctor_id"],
        )

        try:
            appointment = book_appointment(
                doctor=doctor,
                patient=request.user,
                slot_time=serializer.validated_data["slot_time"],
            )
        except AppointmentError as exc:
            raise ValidationError({"detail": str(exc)}) from exc

        return Response(
            self.get_serializer(appointment).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["patch"])
    def cancel(self, request, pk=None):
        appointment = self.get_object()

        serializer = CancelAppointmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            appointment = cancel_appointment(
                appointment=appointment,
                reason=serializer.validated_data["reason"],
            )
        except AppointmentError as exc:
            raise ValidationError({"detail": str(exc)}) from exc

        return Response(self.get_serializer(appointment).data)

    @action(detail=True, methods=["patch"])
    def reschedule(self, request, pk=None):
        appointment = self.get_object()

        serializer = RescheduleAppointmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            appointment = reschedule_appointment(
                appointment=appointment,
                new_slot_time=serializer.validated_data["slot_time"],
            )
        except AppointmentError as exc:
            raise ValidationError({"detail": str(exc)}) from exc

        return Response(self.get_serializer(appointment).data)


class PatientViewSet(RetrieveModelMixin, GenericViewSet):
    permission_classes = [IsAuthenticated, IsPatient]
    queryset = get_user_model().objects.all()

    def get_object(self):
        if str(self.request.user.pk) != self.kwargs["pk"]:
            raise PermissionDenied("You can only view your own appointments.")

        return self.request.user

    @action(detail=True, methods=["get"])
    def appointments(self, request, pk=None):
        appointments = (
            Appointment.objects.select_related("doctor__user", "patient")
            .filter(
                patient=self.get_object(),
                status=Appointment.Status.ACTIVE,
            )
            .order_by("slot_time")
        )

        return Response(AppointmentSerializer(appointments, many=True).data)
