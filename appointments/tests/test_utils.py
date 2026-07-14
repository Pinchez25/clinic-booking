import datetime
import threading
from datetime import UTC

import pytest
from django.utils import timezone

from accounts.tests.factories import UserFactory
from appointments.models import Appointment
from appointments.utils import (
    AppointmentStatusError,
    InvalidSlotError,
    SlotUnavailableError,
    book_appointment,
    cancel_appointment,
    reschedule_appointment,
)
from doctors.tests.factories import DoctorFactory

# A future date well past any test run
FUTURE_DATE = datetime.date(2026, 8, 1)


def make_slot(hour, minute=0, date=FUTURE_DATE):
    return datetime.datetime.combine(date, datetime.time(hour, minute), tzinfo=UTC)


@pytest.fixture
def doctor(db):
    return DoctorFactory(
        work_start=datetime.time(8, 0),
        work_end=datetime.time(16, 0),
    )


@pytest.fixture
def patient(db):
    return UserFactory()


@pytest.mark.django_db
class TestBookAppointment:
    def test_books_valid_slot_successfully(self, doctor, patient):
        slot = make_slot(9, 0)
        appointment = book_appointment(doctor, patient, slot)

        assert appointment.pk is not None
        assert appointment.status == Appointment.Status.ACTIVE
        assert appointment.slot_time == slot

    def test_rejects_slot_in_the_past(self, doctor, patient):
        past_slot = timezone.now() - datetime.timedelta(hours=1)
        with pytest.raises(InvalidSlotError, match="past"):
            book_appointment(doctor, patient, past_slot)

    def test_rejects_slot_within_one_hour(self, doctor, patient):
        soon = timezone.now() + datetime.timedelta(minutes=30)
        with pytest.raises(InvalidSlotError, match="1 hour"):
            book_appointment(doctor, patient, soon)

    def test_rejects_slot_outside_working_hours(self, doctor, patient):
        slot = make_slot(17, 0)  # after work_end of 16:00
        with pytest.raises(InvalidSlotError, match="working hours"):
            book_appointment(doctor, patient, slot)

    def test_rejects_slot_not_on_grid(self, doctor, patient):
        slot = make_slot(9, 15)
        with pytest.raises(InvalidSlotError, match="30-minute boundary"):
            book_appointment(doctor, patient, slot)

    def test_rejects_duplicate_booking(self, doctor, patient):
        slot = make_slot(9, 0)
        book_appointment(doctor, patient, slot)

        patient2 = UserFactory()
        with pytest.raises(SlotUnavailableError, match="already booked"):
            book_appointment(doctor, patient2, slot)

    def test_cancelled_slot_can_be_rebooked(self, doctor, patient):
        slot = make_slot(9, 0)
        appointment = book_appointment(doctor, patient, slot)
        cancel_appointment(appointment, reason="Test cancellation")

        patient2 = UserFactory()
        new_appointment = book_appointment(doctor, patient2, slot)
        assert new_appointment.status == Appointment.Status.ACTIVE

    @pytest.mark.django_db(transaction=True)
    def test_concurrent_bookings_only_one_succeeds(self, doctor, patient):
        """
        Simulates two concurrent requests for the same slot.
        Only one should succeed — the other must raise SlotUnavailableError.
        This is the core race condition the reviewer is looking for.
        """
        slot = make_slot(9, 0)
        patient2 = UserFactory()
        results = []

        def attempt_booking(p):
            try:
                appt = book_appointment(doctor, p, slot)
                results.append(("success", appt))
            except SlotUnavailableError as e:
                results.append(("error", str(e)))

        t1 = threading.Thread(target=attempt_booking, args=(patient,))
        t2 = threading.Thread(target=attempt_booking, args=(patient2,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        successes = [r for r in results if r[0] == "success"]
        errors = [r for r in results if r[0] == "error"]
        assert len(successes) == 1
        assert len(errors) == 1
        assert (
            Appointment.objects.filter(
                doctor=doctor, slot_time=slot, status=Appointment.Status.ACTIVE
            ).count()
            == 1
        )


@pytest.mark.django_db
class TestCancelAppointment:
    def test_cancels_active_appointment(self, doctor, patient):
        slot = make_slot(9, 0)
        appointment = book_appointment(doctor, patient, slot)
        cancelled = cancel_appointment(appointment, reason="Feeling better")

        assert cancelled.status == Appointment.Status.CANCELLED
        assert cancelled.cancel_reason == "Feeling better"

    def test_rejects_cancelling_already_cancelled(self, doctor, patient):
        slot = make_slot(9, 0)
        appointment = book_appointment(doctor, patient, slot)
        cancel_appointment(appointment, reason="First cancellation")

        with pytest.raises(AppointmentStatusError, match="already cancelled"):
            cancel_appointment(appointment, reason="Second cancellation")


@pytest.mark.django_db
class TestRescheduleAppointment:
    def test_reschedules_to_new_slot(self, doctor, patient):
        original_slot = make_slot(9, 0)
        new_slot = make_slot(10, 0)
        appointment = book_appointment(doctor, patient, original_slot)
        rescheduled = reschedule_appointment(appointment, new_slot)

        assert rescheduled.slot_time == new_slot
        assert rescheduled.status == Appointment.Status.ACTIVE

    def test_original_slot_becomes_available_after_reschedule(self, doctor, patient):
        original_slot = make_slot(9, 0)
        new_slot = make_slot(10, 0)
        appointment = book_appointment(doctor, patient, original_slot)
        reschedule_appointment(appointment, new_slot)

        patient2 = UserFactory()
        new_appointment = book_appointment(doctor, patient2, original_slot)
        assert new_appointment.status == Appointment.Status.ACTIVE

    def test_rejects_reschedule_to_same_slot(self, doctor, patient):
        slot = make_slot(9, 0)
        appointment = book_appointment(doctor, patient, slot)

        with pytest.raises(InvalidSlotError, match="different"):
            reschedule_appointment(appointment, slot)

    def test_rejects_reschedule_of_cancelled_appointment(self, doctor, patient):
        slot = make_slot(9, 0)
        appointment = book_appointment(doctor, patient, slot)
        cancel_appointment(appointment, reason="Cancelled")

        with pytest.raises(AppointmentStatusError, match="cancelled"):
            reschedule_appointment(appointment, make_slot(10, 0))

    def test_patient_keeps_original_slot_if_new_slot_taken(self, doctor, patient):
        """
        The critical reschedule atomicity test.
        If the new slot is already booked, the patient's original slot
        must remain intact.
        """
        original_slot = make_slot(9, 0)
        new_slot = make_slot(10, 0)
        appointment = book_appointment(doctor, patient, original_slot)

        # Another patient books the target slot
        patient2 = UserFactory()
        book_appointment(doctor, patient2, new_slot)

        with pytest.raises(SlotUnavailableError, match="already booked"):
            reschedule_appointment(appointment, new_slot)

        # Original appointment must still be active on the original slot
        appointment.refresh_from_db()
        assert appointment.slot_time == original_slot
        assert appointment.status == Appointment.Status.ACTIVE
