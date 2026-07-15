import logging
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from appointments.models import Appointment
from doctors.models import Doctor
from doctors.utils import is_valid_slot

User = get_user_model()

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
    """
    All booking business rules live here — not in serializers.
    Serializers validate shape and type; services validate business logic.
    """
    now = timezone.now()

    if slot_time <= now:
        raise InvalidSlotError("Cannot book a slot in the past.")

    if slot_time < now + BOOKING_BUFFER:
        raise InvalidSlotError("Slots must be booked at least 1 hour in advance.")

    if not is_valid_slot(doctor, slot_time):
        raise InvalidSlotError(
            "Slot does not fall within the doctor's working hours "
            "or is not on a 30-minute boundary."
        )


def book_appointment(doctor: Doctor, patient: User, slot_time) -> Appointment:
    """
    Book a slot for a patient with a doctor.

    The partial unique constraint on (doctor, slot_time) WHERE status='active'
    is the concurrency guard — it enforces the invariant at the DB level.
    IntegrityError on concurrent inserts is caught and raised as SlotUnavailableError.
    select_for_update() is not used here because there is no existing row to lock
    when making a new booking — the constraint does the job.
    """
    _validate_slot_time(doctor, slot_time)

    try:
        appointment = Appointment.objects.create(
            doctor=doctor,
            patient=patient,
            slot_time=slot_time,
        )
    except IntegrityError:
        raise SlotUnavailableError("This slot is already booked.") from None

    logger.info(
        "Appointment booked: id=%s doctor=%s patient=%s slot=%s",
        appointment.id,
        doctor.id,
        patient.id,
        slot_time,
    )
    return appointment


def cancel_appointment(appointment: Appointment, reason: str) -> Appointment:
    """
    Cancel an active appointment with a reason.
    Wrapped in atomic() + select_for_update() to prevent concurrent
    cancel/reschedule operations from racing on the same appointment.
    """
    try:
        with transaction.atomic():
            locked = Appointment.objects.select_for_update().get(
                pk=appointment.pk, status=Appointment.Status.ACTIVE
            )
            locked.status = Appointment.Status.CANCELLED
            locked.cancel_reason = reason
            locked.save(update_fields=["status", "cancel_reason", "updated_at"])
    except Appointment.DoesNotExist:
        raise AppointmentStatusError("This appointment is already cancelled.") from None

    logger.info("Appointment cancelled: id=%s reason=%s", locked.id, reason)
    return locked


def reschedule_appointment(appointment: Appointment, new_slot_time) -> Appointment:
    """
    Move an appointment to a new slot atomically.

    The original slot is only released after the new one is confirmed.
    If the new slot is already taken, IntegrityError fires inside the atomic
    block, the transaction rolls back, and the patient keeps their original booking.

    select_for_update() on the appointment row prevents concurrent reschedule
    or cancel operations from modifying the same appointment simultaneously.
    The unique constraint handles the new slot conflict — no need to lock it.
    """
    if appointment.slot_time == new_slot_time:
        raise InvalidSlotError("New slot time must be different from the current slot.")

    _validate_slot_time(appointment.doctor, new_slot_time)

    try:
        with transaction.atomic():
            locked = Appointment.objects.select_for_update().get(
                pk=appointment.pk, status=Appointment.Status.ACTIVE
            )
            locked.slot_time = new_slot_time
            locked.save(update_fields=["slot_time", "updated_at"])

    except Appointment.DoesNotExist:
        raise AppointmentStatusError("Cannot reschedule a cancelled appointment.") from None
    except IntegrityError:
        raise SlotUnavailableError("The requested slot is already booked.") from None

    logger.info(
        "Appointment rescheduled: id=%s new_slot=%s",
        locked.id,
        new_slot_time,
    )
    return locked
