from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["email", "first_name", "last_name", "role", "is_active", "date_joined"]
    list_filter = ["role", "is_active", "is_staff"]
    search_fields = ["email", "first_name", "last_name"]
    ordering = ["-date_joined"]
    list_select_related = []

    fieldsets = (*BaseUserAdmin.fieldsets, ("Role", {"fields": ("role",)}))
    add_fieldsets = (*BaseUserAdmin.add_fieldsets, ("Role", {"fields": ("role",)}))
