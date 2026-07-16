import logging
from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from doctors.models import Doctor
from doctors.utils import is_valid_slot

from .exceptions import (
    AppointmentError,
    AppointmentStatusError,
    InvalidSlotError,
    SlotUnavailableError,
)
from .models import Appointment

User = get_user_model()

logger = logging.getLogger("appointments")

APPOINTMENT_BOOKING_BUFFER = timedelta(hours=1)


def _validate_slot_time(
    doctor: Doctor,
    patient: User,
    slot_time: datetime,
) -> None:
    now = timezone.now()

    if not patient.has_role(User.Role.PATIENT):
        raise AppointmentError("Only patients can book appointments.")

    if not doctor.is_available:
        raise InvalidSlotError("Doctor is currently unavailable.")

    if slot_time <= now:
        raise InvalidSlotError("Cannot book a slot in the past.")

    if slot_time < now + APPOINTMENT_BOOKING_BUFFER:
        raise InvalidSlotError("Appointments must be booked at least one hour in advance.")

    if not is_valid_slot(doctor, slot_time):
        raise InvalidSlotError(
            "Slot does not fall within the doctor's working hours or is not on a 30-minute boundary."
        )


def book_appointment(
    doctor: Doctor,
    patient: User,
    slot_time: datetime,
) -> Appointment:
    _validate_slot_time(doctor, patient, slot_time)

    try:
        with transaction.atomic():
            appointment = Appointment.objects.create(
                doctor=doctor,
                patient=patient,
                slot_time=slot_time,
            )
    except IntegrityError:
        raise SlotUnavailableError(
            "The requested appointment slot is no longer available."
        ) from None

    logger.info(
        "Appointment booked: id=%s doctor=%s patient=%s slot=%s",
        appointment.id,
        doctor.id,
        patient.id,
        slot_time,
    )

    return appointment


def cancel_appointment(
    appointment: Appointment,
    reason: str,
) -> Appointment:
    try:
        with transaction.atomic():
            appointment = Appointment.objects.select_for_update().get(
                pk=appointment.pk,
                status=Appointment.Status.ACTIVE,
            )

            appointment.status = Appointment.Status.CANCELLED
            appointment.cancel_reason = reason
            appointment.save(
                update_fields=[
                    "status",
                    "cancel_reason",
                    "updated_at",
                ]
            )

    except Appointment.DoesNotExist:
        raise AppointmentStatusError("This appointment has already been cancelled.") from None

    logger.info(
        "Appointment cancelled: id=%s",
        appointment.id,
    )

    return appointment


def _cancel_appointments(appointments: list[Appointment], reason: str) -> list[Appointment]:
    if not appointments:
        return []

    for appointment in appointments:
        appointment.status = Appointment.Status.CANCELLED
        appointment.cancel_reason = reason

    Appointment.objects.bulk_update(
        appointments,
        fields=["status", "cancel_reason", "updated_at"],
    )
    return appointments


def cancel_appointments_for_day(
    doctor: Doctor,
    target_date: date,
    reason: str,
) -> list[Appointment]:
    with transaction.atomic():
        appointments = list(
            Appointment.objects.select_for_update().filter(
                doctor=doctor,
                status=Appointment.Status.ACTIVE,
                slot_time__date=target_date,
            )
        )

        _cancel_appointments(appointments, reason)

    logger.info(
        "Cancelled %s appointments for doctor=%s date=%s",
        len(appointments),
        doctor.id,
        target_date,
    )
    return appointments


def update_doctor_working_hours(
    doctor: Doctor,
    work_start: time,
    work_end: time,
    reason: str,
) -> Doctor:
    with transaction.atomic():
        doctor = Doctor.objects.select_for_update().get(pk=doctor.pk)
        doctor.work_start = work_start
        doctor.work_end = work_end
        doctor.save(update_fields=["work_start", "work_end", "updated_at"])

        appointments = list(
            Appointment.objects.select_for_update().filter(
                doctor=doctor,
                status=Appointment.Status.ACTIVE,
                slot_time__gte=timezone.now(),
            )
        )
        affected_appointments = [
            appointment
            for appointment in appointments
            if not is_valid_slot(doctor, appointment.slot_time)
        ]
        _cancel_appointments(affected_appointments, reason)

    logger.info(
        "Updated working hours for doctor=%s and cancelled %s affected appointments",
        doctor.id,
        len(affected_appointments),
    )
    return doctor


def reschedule_appointment(
    appointment: Appointment,
    new_slot_time: datetime,
) -> Appointment:
    if appointment.slot_time == new_slot_time:
        raise InvalidSlotError("New slot time must be different from the current slot.")

    _validate_slot_time(
        doctor=appointment.doctor,
        patient=appointment.patient,
        slot_time=new_slot_time,
    )

    try:
        with transaction.atomic():
            appointment = Appointment.objects.select_for_update().get(
                pk=appointment.pk,
                status=Appointment.Status.ACTIVE,
            )

            appointment.slot_time = new_slot_time

            appointment.save(
                update_fields=[
                    "slot_time",
                    "updated_at",
                ]
            )

    except Appointment.DoesNotExist:
        raise AppointmentStatusError("Cannot reschedule a cancelled appointment.") from None

    except IntegrityError:
        raise SlotUnavailableError(
            "The requested appointment slot is no longer available."
        ) from None

    logger.info(
        "Appointment rescheduled: id=%s new_slot=%s",
        appointment.id,
        new_slot_time,
    )

    return appointment
