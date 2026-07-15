import datetime
import zoneinfo
from datetime import UTC

import pytest

from accounts.tests.factories import UserFactory
from appointments.models import Appointment
from doctors.tests.factories import DoctorFactory, OvernightDoctorFactory
from doctors.utils import generate_slots, get_available_slots, is_valid_slot

CLINIC_TZ = zoneinfo.ZoneInfo("Africa/Nairobi")
TARGET_DATE = datetime.date(2025, 6, 15)


def clinic_slot(hour, minute=0, date=TARGET_DATE) -> datetime.datetime:
    """Build a UTC-aware datetime from a clinic-local time."""
    return datetime.datetime(
        date.year, date.month, date.day, hour, minute, tzinfo=CLINIC_TZ
    ).astimezone(UTC)


@pytest.mark.django_db
class TestGenerateSlots:
    def test_generates_correct_number_of_slots(self):
        # 08:00 - 16:00 clinic time = 8 hours = 16 slots
        doctor = DoctorFactory(
            work_start=datetime.time(8, 0),
            work_end=datetime.time(16, 0),
        )
        slots = generate_slots(doctor, TARGET_DATE)

        assert len(slots) == 16

    def test_first_slot_matches_work_start_in_utc(self):
        doctor = DoctorFactory(
            work_start=datetime.time(8, 0),
            work_end=datetime.time(16, 0),
        )
        slots = generate_slots(doctor, TARGET_DATE)

        # 08:00 EAT = 05:00 UTC
        assert slots[0] == clinic_slot(8, 0)

    def test_last_slot_is_30_minutes_before_work_end(self):
        doctor = DoctorFactory(
            work_start=datetime.time(8, 0),
            work_end=datetime.time(16, 0),
        )
        slots = generate_slots(doctor, TARGET_DATE)

        # Last slot is 15:30 EAT = 12:30 UTC
        assert slots[-1] == clinic_slot(15, 30)

    def test_all_slots_are_utc_aware(self):
        doctor = DoctorFactory()
        slots = generate_slots(doctor, TARGET_DATE)

        for slot in slots:
            assert slot.tzinfo == UTC

    def test_overnight_shift_generates_slots_across_midnight(self):
        # 22:00 - 06:00 clinic time = 8 hours = 16 slots
        doctor = OvernightDoctorFactory()
        slots = generate_slots(doctor, TARGET_DATE)

        assert len(slots) == 16
        assert slots[0] == clinic_slot(22, 0)
        # Last slot is 05:30 clinic time on the next day
        next_day = TARGET_DATE + datetime.timedelta(days=1)
        assert slots[-1] == clinic_slot(5, 30, date=next_day)


@pytest.mark.django_db
class TestGetAvailableSlots:
    def test_all_slots_available_when_no_bookings(self):
        doctor = DoctorFactory(
            work_start=datetime.time(8, 0),
            work_end=datetime.time(16, 0),
        )
        slots = get_available_slots(doctor, TARGET_DATE)

        assert len(slots) == 16

    def test_booked_slot_excluded_from_available(self):

        doctor = DoctorFactory(
            work_start=datetime.time(8, 0),
            work_end=datetime.time(16, 0),
        )
        patient = UserFactory()
        slot_time = clinic_slot(9, 0)
        Appointment.objects.create(
            doctor=doctor,
            patient=patient,
            slot_time=slot_time,
            status=Appointment.Status.ACTIVE,
        )

        slots = get_available_slots(doctor, TARGET_DATE)

        assert slot_time not in slots
        assert len(slots) == 15

    def test_cancelled_booking_frees_slot(self):

        doctor = DoctorFactory(
            work_start=datetime.time(8, 0),
            work_end=datetime.time(16, 0),
        )
        patient = UserFactory()
        slot_time = clinic_slot(9, 0)
        Appointment.objects.create(
            doctor=doctor,
            patient=patient,
            slot_time=slot_time,
            status=Appointment.Status.CANCELLED,
        )

        slots = get_available_slots(doctor, TARGET_DATE)

        assert slot_time in slots
        assert len(slots) == 16


@pytest.mark.django_db
class TestIsValidSlot:
    def test_valid_slot_on_hour(self):
        doctor = DoctorFactory(
            work_start=datetime.time(8, 0),
            work_end=datetime.time(16, 0),
        )
        assert is_valid_slot(doctor, clinic_slot(9, 0)) is True

    def test_valid_slot_on_half_hour(self):
        doctor = DoctorFactory(
            work_start=datetime.time(8, 0),
            work_end=datetime.time(16, 0),
        )
        assert is_valid_slot(doctor, clinic_slot(9, 30)) is True

    def test_invalid_slot_not_on_grid(self):
        doctor = DoctorFactory(
            work_start=datetime.time(8, 0),
            work_end=datetime.time(16, 0),
        )
        # Build a non-grid UTC time — 09:15 EAT = 06:15 UTC
        slot = datetime.datetime(2025, 6, 15, 6, 15, tzinfo=UTC)
        assert is_valid_slot(doctor, slot) is False

    def test_invalid_slot_before_work_start(self):
        doctor = DoctorFactory(
            work_start=datetime.time(8, 0),
            work_end=datetime.time(16, 0),
        )
        assert is_valid_slot(doctor, clinic_slot(7, 0)) is False

    def test_invalid_slot_at_work_end(self):
        # work_end itself is not a valid slot
        doctor = DoctorFactory(
            work_start=datetime.time(8, 0),
            work_end=datetime.time(16, 0),
        )
        assert is_valid_slot(doctor, clinic_slot(16, 0)) is False

    def test_overnight_valid_slot_before_midnight(self):
        doctor = OvernightDoctorFactory()
        assert is_valid_slot(doctor, clinic_slot(23, 0)) is True

    def test_overnight_valid_slot_after_midnight(self):
        doctor = OvernightDoctorFactory()
        next_day = TARGET_DATE + datetime.timedelta(days=1)
        assert is_valid_slot(doctor, clinic_slot(2, 0, date=next_day)) is True

    def test_overnight_invalid_slot_outside_shift(self):
        doctor = OvernightDoctorFactory()
        assert is_valid_slot(doctor, clinic_slot(12, 0)) is False
