import datetime
from datetime import UTC

import factory
from factory.django import DjangoModelFactory

from accounts.tests.factories import UserFactory
from appointments.models import Appointment
from doctors.tests.factories import DoctorFactory


class AppointmentFactory(DjangoModelFactory):
    class Meta:
        model = Appointment

    doctor = factory.SubFactory(DoctorFactory)
    patient = factory.SubFactory(UserFactory)
    slot_time = factory.LazyFunction(lambda: datetime.datetime(2026, 8, 1, 9, 0, tzinfo=UTC))
    status = Appointment.Status.ACTIVE
