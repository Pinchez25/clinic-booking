from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from accounts.models import User

from .models import Doctor


@receiver(post_save, sender=Doctor)
def assign_doctor_role(sender, instance, created, **kwargs):
    if not created:
        return

    transaction.on_commit(
        lambda: User.objects.filter(
            pk=instance.user_id,
            role=User.Role.PATIENT,
        ).update(role=User.Role.DOCTOR)
    )


@receiver(post_delete, sender=Doctor)
def remove_doctor_role(sender, instance, **kwargs):
    User.objects.filter(
        pk=instance.user_id,
        role=User.Role.DOCTOR,
    ).update(role=User.Role.PATIENT)
