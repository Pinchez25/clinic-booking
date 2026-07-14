from datetime import UTC, date, datetime, timedelta

from .models import Doctor

SLOT_DURATION = timedelta(minutes=30)


def generate_slots(doctor: Doctor, target_date: date) -> list[datetime]:

    slots = []
    current = datetime.combine(target_date, doctor.work_start, tzinfo=UTC)

    if doctor.is_overnight:
        end = datetime.combine(target_date + timedelta(days=1), doctor.work_end, tzinfo=UTC)
    else:
        end = datetime.combine(target_date, doctor.work_end, tzinfo=UTC)

    while current < end:
        slots.append(current)
        current += SLOT_DURATION
    return slots


def get_available_slots(doctor: Doctor, target_date: date) -> list[datetime]:
    all_slots = generate_slots(doctor, target_date)
    if not all_slots:
        return []
    # TODO(#123): Replace this placeholder with an Appointment query once the
    # Appointment model has been implemented.
    booked: set = set()
    return [slot for slot in all_slots if slot not in booked]


def is_valid_slot(doctor: Doctor, slot_time: datetime) -> bool:
    if slot_time.minute not in (0, 30) or slot_time.second != 0 or slot_time.microsecond != 0:
        return False

    slot_as_time = slot_time.time().replace(tzinfo=None)
    start = doctor.work_start
    end = doctor.work_end

    if doctor.is_overnight:
        return slot_as_time >= start or slot_as_time < end
    return start <= slot_as_time < end
