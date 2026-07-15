import base64
import json

import pytest
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from ..models import User
from .factories import UserFactory


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def patient(db):
    return UserFactory()


@pytest.fixture
def auth_client(patient):
    client = APIClient()
    client.force_authenticate(user=patient)
    return client, patient


@pytest.mark.django_db
class TestRegisterAction:
    def test_registers_patient_successfully(self, client):
        payload = {
            "email": "new@example.com",
            "first_name": "Jane",
            "last_name": "Doe",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
        }
        response = client.post("/api/auth/register/", payload)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["user"]["email"] == "new@example.com"
        assert response.data["user"]["role"] == User.Role.PATIENT
        assert "password" not in response.data

    def test_password_mismatch_returns_400(self, client):
        payload = {
            "email": "new@example.com",
            "password": "StrongPass123!",
            "password_confirm": "WrongPass123!",
        }
        response = client.post("/api/auth/register/", payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "password_confirm" in response.data

    def test_duplicate_email_returns_400(self, client, patient):
        payload = {
            "email": patient.email,
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
        }
        response = client.post("/api/auth/register/", payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_weak_password_returns_400(self, client):
        payload = {
            "email": "new@example.com",
            "password": "123",
            "password_confirm": "123",
        }
        response = client.post("/api/auth/register/", payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestLoginView:
    def test_login_returns_token_pair(self, client, patient):
        response = client.post(
            "/api/auth/login/",
            {"email": patient.email, "password": "testpass123"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data

    def test_invalid_credentials_returns_401(self, client, patient):
        response = client.post(
            "/api/auth/login/",
            {"email": patient.email, "password": "wrongpassword"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_jwt_payload_contains_role(self, client, patient):
        response = client.post(
            "/api/auth/login/",
            {"email": patient.email, "password": "testpass123"},
        )
        access = response.data["access"]
        payload_b64 = access.split(".")[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.b64decode(payload_b64))

        assert payload["role"] == User.Role.PATIENT


@pytest.mark.django_db
class TestTokenRefreshView:
    def test_returns_new_access_token(self, client, patient):
        login = client.post(
            "/api/auth/login/",
            {"email": patient.email, "password": "testpass123"},
        )
        response = client.post("/api/auth/token/refresh/", {"refresh": login.data["refresh"]})

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data

    def test_invalid_token_returns_401(self, client):
        response = client.post("/api/auth/token/refresh/", {"refresh": "notavalidtoken"})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestLogoutAction:
    def test_blacklists_refresh_token(self, auth_client, patient):
        client, _ = auth_client
        refresh = str(RefreshToken.for_user(patient))

        response = client.post("/api/auth/logout/", {"refresh": refresh})

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_blacklisted_token_cannot_be_reused(self, auth_client, patient):
        client, _ = auth_client
        refresh = str(RefreshToken.for_user(patient))
        client.post("/api/auth/logout/", {"refresh": refresh})

        response = client.post("/api/auth/token/refresh/", {"refresh": refresh})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_missing_refresh_token_returns_400(self, auth_client):
        client, _ = auth_client
        response = client.post("/api/auth/logout/", {})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unauthenticated_returns_401(self, client):
        response = client.post("/api/auth/logout/", {"refresh": "sometoken"})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestMeAction:
    def test_returns_current_user(self, auth_client):
        client, patient = auth_client
        response = client.get("/api/auth/me/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == patient.email
        assert "password" not in response.data

    def test_unauthenticated_returns_401(self, client):
        response = client.get("/api/auth/me/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
