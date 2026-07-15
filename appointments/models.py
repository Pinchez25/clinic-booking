import uuid

from django.db import models


class Appointment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    doctor = models.ForeignKey(
        "doctors.Doctor", on_delete=models.PROTECT, related_name="appointments"
    )
    patient = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="appointments"
    )
    slot_time = models.DateTimeField()
    status = models.CharField(max_length=10, choices=Status, default=Status.ACTIVE, db_index=True)
    cancel_reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Appointment"
        verbose_name_plural = "Appointments"

        constraints = [
            models.UniqueConstraint(
                fields=["doctor", "slot_time"],
                condition=models.Q(status="ACTIVE"),
                name="unique_active_appointment_per_doctor_slot",
            ),
            models.UniqueConstraint(
                fields=["patient", "slot_time"],
                condition=models.Q(status="ACTIVE"),
                name="unique_active_appointment_per_patient_slot",
            ),
        ]

    def __str__(self):
        return f"{self.patient} with {self.doctor} on {self.slot_time}"

    @property
    def is_active(self) -> bool:
        return self.status == self.Status.ACTIVE

    @property
    def is_cancelled(self) -> bool:
        return self.status == self.Status.CANCELLED
