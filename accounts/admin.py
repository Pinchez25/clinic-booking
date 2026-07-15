from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    ordering = ("-date_joined",)

    list_display = (
        "email",
        "role",
        "is_staff",
        "is_superuser",
        "is_active",
        "date_joined",
    )

    list_filter = (
        "role",
        "is_staff",
        "is_superuser",
        "is_active",
        "groups",
    )

    search_fields = ("email",)

    readonly_fields = (
        "last_login",
        "date_joined",
    )

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "email",
                    "password",
                )
            },
        ),
        ("Personal info", {"fields": ()}),
        ("Role", {"fields": ("role",)}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            "Important dates",
            {
                "fields": (
                    "last_login",
                    "date_joined",
                )
            },
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "role",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_superuser",
                    "is_active",
                ),
            },
        ),
    )
