import datetime
from datetime import UTC

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.tests.factories import UserFactory
from appointments.models import Appointment
from appointments.tests.factories import AppointmentFactory
from doctors.tests.factories import DoctorFactory


def make_slot(hour, minute=0):
    return datetime.datetime(2026, 8, 1, hour, minute, tzinfo=UTC).isoformat()


@pytest.fixture
def patient(db):
    return UserFactory()


@pytest.fixture
def doctor(db):
    return DoctorFactory(
        work_start=datetime.time(8, 0),
        work_end=datetime.time(16, 0),
    )


@pytest.fixture
def auth_client(patient):
    client = APIClient()
    client.force_authenticate(user=patient)
    return client, patient


@pytest.mark.django_db
class TestBookAppointment:
    def test_books_appointment_successfully(self, auth_client, doctor):
        client, patient = auth_client
        response = client.post(
            "/api/appointments/",
            {"doctor_id": str(doctor.id), "slot_time": make_slot(9)},
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == Appointment.Status.ACTIVE
        assert response.data["doctor"]["id"] == str(doctor.id)
        assert response.data["patient"]["id"] == str(patient.id)

    def test_doctor_cannot_book(self, doctor):
        client = APIClient()
        client.force_authenticate(user=doctor.user)
        response = client.post(
            "/api/appointments/",
            {"doctor_id": str(doctor.id), "slot_time": make_slot(9)},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_returns_401(self):
        response = APIClient().post("/api/appointments/", {})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_doctor_returns_404(self, auth_client):
        client, _ = auth_client
        response = client.post(
            "/api/appointments/",
            {
                "doctor_id": "00000000-0000-0000-0000-000000000000",
                "slot_time": make_slot(9),
            },
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_slot_outside_working_hours_returns_400(self, auth_client, doctor):
        client, _ = auth_client
        response = client.post(
            "/api/appointments/",
            {"doctor_id": str(doctor.id), "slot_time": make_slot(17)},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_duplicate_slot_returns_400(self, auth_client, doctor, patient):
        client, _ = auth_client
        AppointmentFactory(
            doctor=doctor,
            patient=patient,
            slot_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
        )
        response = client.post(
            "/api/appointments/",
            {"doctor_id": str(doctor.id), "slot_time": make_slot(9)},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_response_does_not_expose_sensitive_fields(self, auth_client, doctor):
        client, _ = auth_client
        response = client.post(
            "/api/appointments/",
            {"doctor_id": str(doctor.id), "slot_time": make_slot(9)},
        )

        assert "personal_phone" not in str(response.data)
        assert "password" not in str(response.data)


@pytest.mark.django_db
class TestCancelAppointment:
    def test_cancels_own_appointment(self, auth_client, doctor, patient):
        client, _ = auth_client
        appointment = AppointmentFactory(
            doctor=doctor,
            patient=patient,
            slot_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
        )
        response = client.patch(
            f"/api/appointments/{appointment.id}/cancel/",
            {"reason": "Feeling better"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == Appointment.Status.CANCELLED
        assert response.data["cancel_reason"] == "Feeling better"

    def test_cannot_cancel_another_patients_appointment(self, doctor, db):
        patient1 = UserFactory()
        patient2 = UserFactory()
        appointment = AppointmentFactory(
            doctor=doctor,
            patient=patient1,
            slot_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
        )
        client = APIClient()
        client.force_authenticate(user=patient2)

        response = client.patch(
            f"/api/appointments/{appointment.id}/cancel/",
            {"reason": "Unauthorized"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cancelling_already_cancelled_returns_400(self, auth_client, doctor, patient):
        client, _ = auth_client
        appointment = AppointmentFactory(
            doctor=doctor,
            patient=patient,
            slot_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
            status=Appointment.Status.CANCELLED,
        )
        response = client.patch(
            f"/api/appointments/{appointment.id}/cancel/",
            {"reason": "Again"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_reason_returns_400(self, auth_client, doctor, patient):
        client, _ = auth_client
        appointment = AppointmentFactory(
            doctor=doctor,
            patient=patient,
            slot_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
        )
        response = client.patch(f"/api/appointments/{appointment.id}/cancel/", {})

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestRescheduleAppointment:
    def test_reschedules_own_appointment(self, auth_client, doctor, patient):
        client, _ = auth_client
        appointment = AppointmentFactory(
            doctor=doctor,
            patient=patient,
            slot_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
        )
        response = client.patch(
            f"/api/appointments/{appointment.id}/reschedule/",
            {"slot_time": make_slot(10)},
        )

        assert response.status_code == status.HTTP_200_OK
        assert "10:00" in response.data["slot_time"]

    def test_cannot_reschedule_another_patients_appointment(self, doctor, db):
        patient1 = UserFactory()
        patient2 = UserFactory()
        appointment = AppointmentFactory(
            doctor=doctor,
            patient=patient1,
            slot_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
        )
        client = APIClient()
        client.force_authenticate(user=patient2)

        response = client.patch(
            f"/api/appointments/{appointment.id}/reschedule/",
            {"slot_time": make_slot(10)},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_rescheduling_cancelled_appointment_returns_400(self, auth_client, doctor, patient):
        client, _ = auth_client
        appointment = AppointmentFactory(
            doctor=doctor,
            patient=patient,
            slot_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
            status=Appointment.Status.CANCELLED,
        )
        response = client.patch(
            f"/api/appointments/{appointment.id}/reschedule/",
            {"slot_time": make_slot(10)},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestPatientAppointments:
    def test_returns_own_upcoming_appointments(self, auth_client, doctor, patient):
        client, _ = auth_client
        AppointmentFactory(
            doctor=doctor,
            patient=patient,
            slot_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
        )
        AppointmentFactory(
            doctor=doctor,
            patient=patient,
            slot_time=datetime.datetime(2026, 8, 1, 10, 0, tzinfo=UTC),
        )
        response = client.get(f"/api/patients/{patient.id}/appointments/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_appointments_sorted_by_slot_time(self, auth_client, doctor, patient):
        client, _ = auth_client
        AppointmentFactory(
            doctor=doctor,
            patient=patient,
            slot_time=datetime.datetime(2026, 8, 1, 10, 0, tzinfo=UTC),
        )
        AppointmentFactory(
            doctor=doctor,
            patient=patient,
            slot_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
        )
        response = client.get(f"/api/patients/{patient.id}/appointments/")

        slots = [a["slot_time"] for a in response.data]
        assert slots == sorted(slots)

    def test_cancelled_appointments_excluded(self, auth_client, doctor, patient):
        client, _ = auth_client
        AppointmentFactory(
            doctor=doctor,
            patient=patient,
            slot_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
            status=Appointment.Status.CANCELLED,
        )
        response = client.get(f"/api/patients/{patient.id}/appointments/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0

    def test_cannot_view_another_patients_appointments(self, auth_client, doctor, db):
        client, _ = auth_client
        other_patient = UserFactory()
        response = client.get(f"/api/patients/{other_patient.id}/appointments/")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_excludes_other_patients_appointments(self, auth_client, doctor, patient):
        client, _ = auth_client
        other_patient = UserFactory()
        AppointmentFactory(
            doctor=doctor,
            patient=other_patient,
            slot_time=datetime.datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
        )
        response = client.get(f"/api/patients/{patient.id}/appointments/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0
