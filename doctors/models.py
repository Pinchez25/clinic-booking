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
        ordering = ["-created_at"]

    def __str__(self):
        return f"Dr. {self.user.get_full_name() or self.user.email}"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def is_overnight(self) -> bool:
        return self.work_end <= self.work_start

    def clean(self):
        if self.work_start == self.work_end:
            raise ValidationError("Work start and end times cannot be the same.")
