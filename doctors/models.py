import uuid

from django.core.exceptions import ValidationError
from django.db import models


class Doctor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        "accounts.User", on_delete=models.CASCADE, related_name="doctor_profile"
    )
    work_start = models.TimeField()
    work_end = models.TimeField()
    is_available = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Doctor"
        verbose_name_plural = "Doctors"
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(work_start=models.F("work_end")),
                name="doctor_work_start_not_equal_work_end",
            )
        ]

    def __str__(self) -> str:
        return f"Dr. {self.user.get_full_name() or self.user.email}"

    @property
    def is_overnight(self) -> bool:
        if self.work_start is None or self.work_end is None:
            return False

        return self.work_end <= self.work_start

    def clean(self):
        if self.work_start == self.work_end:
            raise ValidationError("work_start and work_end cannot be the same time.")
