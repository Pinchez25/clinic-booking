import uuid

import pytest
from django.db import IntegrityError

from ..models import User
from .factories import AdminUserFactory, DoctorUserFactory, UserFactory


@pytest.mark.django_db
class TestUserModel:
    def test_str_returns_email(self):
        user = UserFactory(email="test@example.com")

        assert str(user) == "test@example.com"

    def test_default_role_is_patient(self):
        user = UserFactory()

        assert user.role == User.Role.PATIENT
        assert user.has_role(User.Role.PATIENT)
        assert not user.has_role(User.Role.DOCTOR)
        assert not user.has_role(User.Role.ADMIN)

    def test_doctor_role(self):
        user = DoctorUserFactory()

        assert user.has_role(User.Role.DOCTOR)
        assert not user.has_role(User.Role.PATIENT)
        assert not user.has_role(User.Role.ADMIN)

    def test_admin_role(self):
        user = AdminUserFactory()

        assert user.has_role(User.Role.ADMIN)
        assert not user.has_role(User.Role.PATIENT)
        assert not user.has_role(User.Role.DOCTOR)

    def test_email_is_unique(self):
        UserFactory(email="unique@example.com")

        with pytest.raises(IntegrityError):
            UserFactory(email="unique@example.com")

    def test_uuid_primary_key(self):
        user = UserFactory()

        assert isinstance(user.id, uuid.UUID)

    def test_create_user_assigns_patient_role(self):
        user = User.objects.create_user(
            email="patient@example.com",
            password="PatientPass123!",
        )

        assert user.role == User.Role.PATIENT
        assert user.has_role(User.Role.PATIENT)
        assert not user.is_staff
        assert not user.is_superuser

    def test_create_superuser_assigns_admin_role(self):
        user = User.objects.create_superuser(
            email="super@example.com",
            password="SuperPass123!",
        )

        assert user.role == User.Role.ADMIN
        assert user.has_role(User.Role.ADMIN)
        assert user.is_staff
        assert user.is_superuser

    def test_create_superuser_requires_is_staff(self):
        with pytest.raises(ValueError, match="is_staff=True"):
            User.objects.create_superuser(
                email="admin@example.com",
                password="password123",
                is_staff=False,
            )

    def test_create_superuser_requires_is_superuser(self):
        with pytest.raises(ValueError, match="is_superuser=True"):
            User.objects.create_superuser(
                email="admin@example.com",
                password="password123",
                is_superuser=False,
            )
