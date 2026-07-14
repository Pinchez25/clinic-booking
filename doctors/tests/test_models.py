import pytest
from django.core.exceptions import ValidationError

from doctors.tests.factories import DoctorFactory, OvernightDoctorFactory


@pytest.mark.django_db
class TestDoctorModel:
    def test_str_returns_full_name(self):
        doctor = DoctorFactory(user__first_name="Amina", user__last_name="Ochieng")
        assert str(doctor) == "Dr. Amina Ochieng"

    def test_str_falls_back_to_email(self):
        doctor = DoctorFactory(user__first_name="", user__last_name="")
        assert str(doctor) == f"Dr. {doctor.user.email}"

    def test_is_overnight_false_for_day_shift(self):
        doctor = DoctorFactory()
        assert doctor.is_overnight is False

    def test_is_overnight_true_for_night_shift(self):
        doctor = OvernightDoctorFactory()
        assert doctor.is_overnight is True

    def test_same_start_and_end_raises_validation_error(self):
        import datetime

        with pytest.raises(ValidationError):
            DoctorFactory(
                work_start=datetime.time(9, 0),
                work_end=datetime.time(9, 0),
            )
