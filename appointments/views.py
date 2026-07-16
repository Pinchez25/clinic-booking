import logging

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.mixins import CreateModelMixin, ListModelMixin, RetrieveModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from accounts.permissions import IsPatient
from accounts.serializers import UserSerializer
from doctors.models import Doctor

from .exceptions import AppointmentError
from .models import Appointment
from .permissions import CanManageAppointment
from .serializers import (
    AppointmentSerializer,
    BookAppointmentSerializer,
    CancelAppointmentSerializer,
    RescheduleAppointmentSerializer,
)
from .utils import (
    book_appointment,
    cancel_appointment,
    reschedule_appointment,
)

logger = logging.getLogger("appointments")

User = get_user_model()


@extend_schema(tags=["Appointments"])
class AppointmentViewSet(
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    GenericViewSet,
):
    queryset = Appointment.objects.select_related(
        "doctor__user",
        "patient",
    )
    serializer_class = AppointmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset().order_by("slot_time")
        user = self.request.user

        if user.has_role(User.Role.ADMIN):
            return queryset

        if user.has_role(User.Role.DOCTOR):
            return queryset.filter(doctor=user.doctor_profile)

        return queryset.filter(patient=user)

    def get_permissions(self):
        permissions = list(super().get_permissions())

        if self.action in {"retrieve", "cancel", "reschedule"}:
            permissions.append(CanManageAppointment())

        return permissions

    @extend_schema(
        summary="Book an appointment",
        description="Create a new appointment for the authenticated patient.",
        request=BookAppointmentSerializer,
        responses={201: AppointmentSerializer},
    )
    def create(self, request, *args, **kwargs):
        if not request.user.has_role(User.Role.PATIENT):
            raise PermissionDenied("Only patients can book appointments.")

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

    @extend_schema(
        summary="Cancel an appointment",
        description="Cancel an existing appointment and optionally supply a reason.",
        operation_id="cancelAppointment",
        request=CancelAppointmentSerializer,
        responses={200: AppointmentSerializer},
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

    @extend_schema(
        summary="Reschedule an appointment",
        description="Move an existing appointment to a new slot.",
        operation_id="rescheduleAppointment",
        request=RescheduleAppointmentSerializer,
        responses={200: AppointmentSerializer},
    )
    @action(detail=True, methods=["patch"])
    def reschedule(self, request, pk=None):
        appointment = self.get_object()

        if appointment.patient_id != request.user.id:
            raise PermissionDenied("You can only reschedule your own appointments.")

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


@extend_schema(tags=["Patients"])
class PatientViewSet(RetrieveModelMixin, GenericViewSet):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsPatient]
    queryset = User.objects.all()

    def get_object(self):
        if str(self.request.user.pk) != self.kwargs["pk"]:
            raise PermissionDenied("You can only view your own profile.")

        return self.request.user

    @extend_schema(
        summary="List active appointments",
        description="Return the authenticated patient's active appointments.",
        operation_id="listPatientAppointments",
        responses={200: AppointmentSerializer(many=True)},
    )
    @action(detail=True, methods=["get"])
    def appointments(self, request, pk=None):
        appointments = (
            Appointment.objects.select_related(
                "doctor__user",
                "patient",
            )
            .filter(
                patient=self.get_object(),
                status=Appointment.Status.ACTIVE,
            )
            .order_by("slot_time")
        )

        return Response(
            AppointmentSerializer(
                appointments,
                many=True,
            ).data
        )
