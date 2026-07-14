import factory
from factory.django import DjangoModelFactory

from accounts.tests.factories import DoctorUserFactory
from doctors.models import Doctor


class DoctorFactory(DjangoModelFactory):
    class Meta:
        model = Doctor

    user = factory.SubFactory(DoctorUserFactory)
    work_start = factory.LazyFunction(lambda: __import__("datetime").time(8, 0))
    work_end = factory.LazyFunction(lambda: __import__("datetime").time(16, 0))
    is_available = True


class OvernightDoctorFactory(DoctorFactory):
    """Night shift doctor — 22:00 to 06:00."""

    work_start = factory.LazyFunction(lambda: __import__("datetime").time(22, 0))
    work_end = factory.LazyFunction(lambda: __import__("datetime").time(6, 0))
