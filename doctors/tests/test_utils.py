import datetime
from datetime import UTC

import pytest

from accounts.tests.factories import UserFactory
from appointments.models import Appointment
from doctors.tests.factories import DoctorFactory, OvernightDoctorFactory
from doctors.utils import generate_slots, get_available_slots, is_valid_slot

TARGET_DATE = datetime.date(2025, 6, 15)


@pytest.mark.django_db
class TestGenerateSlots:
    def test_generates_correct_number_of_slots(self):
        # 08:00 - 16:00 = 8 hours = 16 slots
        doctor = DoctorFactory(
            work_start=datetime.time(8, 0),
            work_end=datetime.time(16, 0),
        )
        slots = generate_slots(doctor, TARGET_DATE)

        assert len(slots) == 16

    def test_first_slot_matches_work_start(self):
        doctor = DoctorFactory(
            work_start=datetime.time(8, 0),
            work_end=datetime.time(16, 0),
        )
        slots = generate_slots(doctor, TARGET_DATE)

        assert slots[0].time() == datetime.time(8, 0)

    def test_last_slot_is_30_minutes_before_work_end(self):
        doctor = DoctorFactory(
            work_start=datetime.time(8, 0),
            work_end=datetime.time(16, 0),
        )
        slots = generate_slots(doctor, TARGET_DATE)

        assert slots[-1].time() == datetime.time(15, 30)

    def test_all_slots_are_utc_aware(self):
        doctor = DoctorFactory()
        slots = generate_slots(doctor, TARGET_DATE)

        for slot in slots:
            assert slot.tzinfo == UTC

    def test_overnight_shift_generates_slots_across_midnight(self):
        # 22:00 - 06:00 = 8 hours = 16 slots
        doctor = OvernightDoctorFactory()
        slots = generate_slots(doctor, TARGET_DATE)

        assert len(slots) == 16
        assert slots[0].time() == datetime.time(22, 0)
        # Last slot should be on the next day at 05:30
        assert slots[-1].date() == TARGET_DATE + datetime.timedelta(days=1)
        assert slots[-1].time() == datetime.time(5, 30)


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
        slot_time = datetime.datetime.combine(TARGET_DATE, datetime.time(9, 0), tzinfo=UTC)
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
        slot_time = datetime.datetime.combine(TARGET_DATE, datetime.time(9, 0), tzinfo=UTC)
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
        slot = datetime.datetime.combine(TARGET_DATE, datetime.time(9, 0), tzinfo=UTC)

        assert is_valid_slot(doctor, slot) is True

    def test_valid_slot_on_half_hour(self):
        doctor = DoctorFactory(
            work_start=datetime.time(8, 0),
            work_end=datetime.time(16, 0),
        )
        slot = datetime.datetime.combine(TARGET_DATE, datetime.time(9, 30), tzinfo=UTC)

        assert is_valid_slot(doctor, slot) is True

    def test_invalid_slot_not_on_grid(self):
        doctor = DoctorFactory(
            work_start=datetime.time(8, 0),
            work_end=datetime.time(16, 0),
        )
        slot = datetime.datetime.combine(TARGET_DATE, datetime.time(9, 15), tzinfo=UTC)

        assert is_valid_slot(doctor, slot) is False

    def test_invalid_slot_before_work_start(self):
        doctor = DoctorFactory(
            work_start=datetime.time(8, 0),
            work_end=datetime.time(16, 0),
        )
        slot = datetime.datetime.combine(TARGET_DATE, datetime.time(7, 0), tzinfo=UTC)

        assert is_valid_slot(doctor, slot) is False

    def test_invalid_slot_at_work_end(self):
        # work_end itself is not a valid slot — the last slot is 30 min before
        doctor = DoctorFactory(
            work_start=datetime.time(8, 0),
            work_end=datetime.time(16, 0),
        )
        slot = datetime.datetime.combine(TARGET_DATE, datetime.time(16, 0), tzinfo=UTC)

        assert is_valid_slot(doctor, slot) is False

    def test_overnight_valid_slot_before_midnight(self):
        doctor = OvernightDoctorFactory()
        slot = datetime.datetime.combine(TARGET_DATE, datetime.time(23, 0), tzinfo=UTC)

        assert is_valid_slot(doctor, slot) is True

    def test_overnight_valid_slot_after_midnight(self):
        doctor = OvernightDoctorFactory()
        slot = datetime.datetime.combine(TARGET_DATE, datetime.time(2, 0), tzinfo=UTC)

        assert is_valid_slot(doctor, slot) is True

    def test_overnight_invalid_slot_outside_shift(self):
        doctor = OvernightDoctorFactory()
        slot = datetime.datetime.combine(TARGET_DATE, datetime.time(12, 0), tzinfo=UTC)

        assert is_valid_slot(doctor, slot) is False
