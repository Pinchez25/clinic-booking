import pytest

from ..models import User
from .factories import DoctorUserFactory, UserFactory


@pytest.mark.django_db
class TestUserModel:
    def test_str_returns_email(self):
        user = UserFactory(email="test@example.com")
        assert str(user) == "test@example.com"

    def test_default_role_is_patient(self):
        user = UserFactory()
        assert user.role == User.Role.PATIENT
        assert user.is_patient is True
        assert user.is_doctor is False

    def test_doctor_role_properties(self):
        user = DoctorUserFactory()
        assert user.is_doctor is True
        assert user.is_patient is False

    def test_email_is_unique(self):
        from django.db import IntegrityError

        UserFactory(email="unique@example.com")
        with pytest.raises(IntegrityError):
            UserFactory(email="unique@example.com")

    def test_uuid_primary_key(self):
        user = UserFactory()
        assert user.id is not None
        assert len(str(user.id)) == 36  # UUID4 string length
