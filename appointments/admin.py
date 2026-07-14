from django.contrib import admin

from appointments.models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ["__str__", "status", "slot_time", "created_at"]
    list_filter = ["status"]
    search_fields = ["patient__email", "doctor__user__email"]
    list_select_related = ["doctor__user", "patient"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-slot_time"]
