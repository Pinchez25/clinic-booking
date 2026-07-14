import logging
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from appointments.models import Appointment
from doctors.models import Doctor
from doctors.utils import is_valid_slot

logger = logging.getLogger("appointments")

BOOKING_BUFFER = timedelta(hours=1)


class AppointmentError(Exception):
    """Base exception for all appointment business rule violations."""


class SlotUnavailableError(AppointmentError):
    pass


class InvalidSlotError(AppointmentError):
    pass


class AppointmentStatusError(AppointmentError):
    pass


def _validate_slot_time(doctor: Doctor, slot_time) -> None:
    now = timezone.now()

    if slot_time <= now:
        raise InvalidSlotError("Cannot book an appointment in the past.")

    if slot_time < now + BOOKING_BUFFER:
        raise InvalidSlotError("Slots must be booked at least 1 hour in advance.")

    if not is_valid_slot(doctor, slot_time):
        raise InvalidSlotError("Slot does not fall within the doctor's working hours.")


def book_appointment(doctor: Doctor, patient, slot_time) -> Appointment:
    _validate_slot_time(doctor, slot_time)

    try:
        with transaction.atomic():
            Appointment.objects.select_for_update().filter(
                doctor=doctor,
                slot_time=slot_time,
                status=Appointment.Status.ACTIVE,
            ).first()

            appointment = Appointment.objects.create(
                doctor=doctor,
                patient=patient,
                slot_time=slot_time,
            )
    except IntegrityError:
        raise SlotUnavailableError("Slot is already booked.") from None

    logger.info(
        "Appointment booked: doctor=%s, patient=%s, slot_time=%s",
        doctor.id,
        patient.id,
        slot_time,
    )
    return appointment


def cancel_appointment(appointment: Appointment, reason: str) -> Appointment:

    if appointment.is_cancelled:
        raise AppointmentStatusError("Appointment is already cancelled.")
    appointment.status = Appointment.Status.CANCELLED
    appointment.cancel_reason = reason
    appointment.save(update_fields=["status", "cancel_reason", "updated_at"])
    logger.info("Appointment cancelled: appointment=%s", appointment.id)
    return appointment


def reschedule_appointment(appointment: Appointment, new_slot_time) -> Appointment:
    if appointment.is_cancelled:
        raise AppointmentStatusError("Cannot reschedule a cancelled appointment.")

    if appointment.slot_time == new_slot_time:
        raise InvalidSlotError("New slot time must be different from the current slot time.")

    _validate_slot_time(appointment.doctor, new_slot_time)

    try:
        with transaction.atomic():
            locked = Appointment.objects.select_for_update().get(
                id=appointment.id, status=Appointment.Status.ACTIVE
            )

            Appointment.objects.select_for_update().filter(
                doctor=locked.doctor,
                slot_time=new_slot_time,
                status=Appointment.Status.ACTIVE,
            ).first()

            locked.slot_time = new_slot_time
            locked.save(update_fields=["slot_time", "updated_at"])
    except Appointment.DoesNotExist:
        raise AppointmentStatusError("Appointment is no longer active.") from None
    except IntegrityError:
        raise SlotUnavailableError("Slot is already booked.") from None
    logger.info(
        "Appointment rescheduled: appointment=%s new_slot=%s", appointment.id, new_slot_time
    )
    appointment.slot_time = new_slot_time
    return appointment
