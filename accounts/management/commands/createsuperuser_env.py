import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create a superuser from environment variables (DJANGO_SUPERUSER_EMAIL, DJANGO_SUPERUSER_PASSWORD)."

    def handle(self, *args, **options):
        User = get_user_model()  # noqa: N806

        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "james@yahoo.com")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "Peter@1234")

        # if not email or not password:
        #     self.stdout.write(
        #         self.style.WARNING(
        #             "Skipping superuser creation: set DJANGO_SUPERUSER_EMAIL and "
        #             "DJANGO_SUPERUSER_PASSWORD to create one."
        #         )
        #     )
        #     return

        if User.objects.filter(email=email).exists():
            self.stdout.write(
                self.style.WARNING(f"Superuser with email {email} already exists. Skipping.")
            )
            return

        User.objects.create_superuser(email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Superuser {email} created successfully."))
