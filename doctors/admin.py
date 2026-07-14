from django.contrib import admin

from .models import Doctor


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ["__str__", "work_start", "work_end", "is_overnight", "is_available"]
    list_filter = ["is_available"]
    search_fields = ["user__email", "user__first_name", "user__last_name"]
    list_select_related = ["user"]
    readonly_fields = ["is_overnight", "created_at", "updated_at"]

    fieldsets = [
        (None, {"fields": ["user", "is_available"]}),
        ("Shift", {"fields": ["work_start", "work_end", "is_overnight"]}),
        ("Timestamps", {"fields": ["created_at", "updated_at"]}),
    ]
