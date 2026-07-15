from django.apps import AppConfig


class DoctorsConfig(AppConfig):
    name = "doctors"

    def ready(self):
        from . import signals  # noqa: F401
