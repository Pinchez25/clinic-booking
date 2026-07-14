import datetime

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.tests.factories import UserFactory
from doctors.tests.factories import DoctorFactory, OvernightDoctorFactory


@pytest.fixture
def client():
    patient = UserFactory()
    client = APIClient()
    client.force_authenticate(user=patient)
    return client


@pytest.mark.django_db
class TestDoctorListView:
    def test_lists_active_doctors(self, client):
        DoctorFactory.create_batch(3)
        response = client.get("/api/doctors/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3

    def test_excludes_inactive_doctors(self, client):
        DoctorFactory(is_available=True)
        DoctorFactory(is_available=False)
        response = client.get("/api/doctors/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_response_does_not_expose_phone_or_personal_details(self, client):
        DoctorFactory()
        response = client.get("/api/doctors/")

        doctor_data = response.data["results"][0]
        assert "personal_phone" not in doctor_data
        assert "password" not in doctor_data
        assert "username" not in doctor_data

    def test_unauthenticated_returns_401(self):
        response = APIClient().get("/api/doctors/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestDoctorAvailabilityAction:
    def test_returns_available_slots(self, client):
        doctor = DoctorFactory(
            work_start=datetime.time(8, 0),
            work_end=datetime.time(10, 0),
        )
        response = client.get(f"/api/doctors/{doctor.id}/availability/?date=2025-06-15")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["available_slots"]) == 4  # 08:00, 08:30, 09:00, 09:30

    def test_missing_date_returns_400(self, client):
        doctor = DoctorFactory()
        response = client.get(f"/api/doctors/{doctor.id}/availability/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_date_format_returns_400(self, client):
        doctor = DoctorFactory()
        response = client.get(f"/api/doctors/{doctor.id}/availability/?date=15-06-2025")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_overnight_doctor_returns_correct_slots(self, client):
        # 22:00 - 06:00 = 16 slots
        doctor = OvernightDoctorFactory()
        response = client.get(f"/api/doctors/{doctor.id}/availability/?date=2025-06-15")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["available_slots"]) == 16

    def test_inactive_doctor_returns_404(self, client):
        doctor = DoctorFactory(is_available=False)
        response = client.get(f"/api/doctors/{doctor.id}/availability/?date=2025-06-15")

        assert response.status_code == status.HTTP_404_NOT_FOUND
