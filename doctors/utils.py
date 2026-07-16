import zoneinfo
from datetime import UTC, date, datetime, timedelta

from django.conf import settings

from appointments.models import Appointment
from doctors.models import Doctor

SLOT_DURATION = timedelta(minutes=30)


def _get_clinic_tz() -> zoneinfo.ZoneInfo:
    """Returns the clinic's configured timezone as a ZoneInfo object."""
    return zoneinfo.ZoneInfo(settings.CLINIC_TIMEZONE)


def generate_slots(doctor: Doctor, target_date: date) -> list[datetime]:
    """
    Generate all 30-minute slot datetimes for a doctor on a given date.

    The doctor's work_start and work_end are interpreted as times in the
    clinic's local timezone (CLINIC_TIMEZONE setting). Slots are returned
    as UTC-aware datetimes so the rest of the application works exclusively
    in UTC. Clients are responsible for converting UTC to their local display
    timezone.

    Handles overnight shifts where work_end <= work_start.
    The target_date is the date the shift STARTS in the clinic's timezone.
    """
    start, end = get_shift_bounds(doctor, target_date)

    slots = []
    current = start

    while current < end:
        slots.append(current)
        current += SLOT_DURATION

    return slots


def get_available_slots(doctor: Doctor, target_date: date) -> list[datetime]:
    """
    Return all slots for a doctor on a given date that are not already booked.
    Imports Appointment here to avoid circular imports between doctors and appointments.
    """
    all_slots = generate_slots(doctor, target_date)
    if not all_slots:
        return []

    booked = set(
        Appointment.objects.filter(
            doctor=doctor,
            slot_time__in=all_slots,
            status=Appointment.Status.ACTIVE,
        ).values_list("slot_time", flat=True)
    )

    return [slot for slot in all_slots if slot not in booked]


def is_valid_slot(doctor: Doctor, slot_time: datetime) -> bool:
    """
    Check that slot_time falls on a valid 30-minute grid boundary
    within the doctor's working hours.

    slot_time is expected to be UTC-aware (as stored and compared throughout
    the application). It is converted to the clinic's local timezone before
    comparing against the doctor's work_start and work_end, which are defined
    in clinic local time.
    """
    if slot_time.minute not in (0, 30) or slot_time.second != 0 or slot_time.microsecond != 0:
        return False

    clinic_tz = _get_clinic_tz()
    local_time = slot_time.astimezone(clinic_tz).time().replace(tzinfo=None)
    start = doctor.work_start
    end = doctor.work_end

    if doctor.is_overnight:
        return local_time >= start or local_time < end
    return start <= local_time < end


def get_shift_bounds(
    doctor: Doctor,
    target_date: date,
) -> tuple[datetime, datetime]:
    """
    Return the UTC start and end datetimes for the doctor's shift that starts
    on target_date in the clinic's local timezone.
    """
    clinic_tz = _get_clinic_tz()

    start = datetime.combine(
        target_date,
        doctor.work_start,
        tzinfo=clinic_tz,
    )

    if doctor.is_overnight:
        end = datetime.combine(
            target_date + timedelta(days=1),
            doctor.work_end,
            tzinfo=clinic_tz,
        )
    else:
        end = datetime.combine(
            target_date,
            doctor.work_end,
            tzinfo=clinic_tz,
        )

    return start.astimezone(UTC), end.astimezone(UTC)
