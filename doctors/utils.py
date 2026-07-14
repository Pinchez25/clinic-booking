from datetime import UTC, date, datetime, timedelta

from appointments.models import Appointment
from doctors.models import Doctor

SLOT_DURATION = timedelta(minutes=30)


def generate_slots(doctor: Doctor, target_date: date) -> list[datetime]:
    """
    Generate all 30-minute slot datetimes for a doctor on a given date.
    Handles overnight shifts where work_end <= work_start.
    All returned datetimes are timezone-aware (UTC).
    """
    slots = []
    current = datetime.combine(target_date, doctor.work_start, tzinfo=UTC)

    if doctor.is_overnight:
        # Shift crosses midnight — end time is on the next day
        end = datetime.combine(target_date + timedelta(days=1), doctor.work_end, tzinfo=UTC)
    else:
        end = datetime.combine(target_date, doctor.work_end, tzinfo=UTC)

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
    """
    if slot_time.minute not in (0, 30) or slot_time.second != 0 or slot_time.microsecond != 0:
        return False

    slot_as_time = slot_time.time().replace(tzinfo=None)
    start = doctor.work_start
    end = doctor.work_end

    if doctor.is_overnight:
        return slot_as_time >= start or slot_as_time < end
    return start <= slot_as_time < end
