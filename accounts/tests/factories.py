import factory
from factory.django import DjangoModelFactory

from ..models import User


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    username = factory.LazyAttribute(lambda o: o.email)
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    password = factory.django.Password("testpass123")
    role = User.Role.PATIENT
    is_active = True


class DoctorUserFactory(UserFactory):
    role = User.Role.DOCTOR
    email = factory.Sequence(lambda n: f"doctor{n}@clinic.com")
    username = factory.LazyAttribute(lambda o: o.email)


class AdminUserFactory(UserFactory):
    role = User.Role.ADMIN
    email = factory.Sequence(lambda n: f"admin{n}@clinic.com")
    username = factory.LazyAttribute(lambda o: o.email)
    is_staff = True
    is_superuser = True
