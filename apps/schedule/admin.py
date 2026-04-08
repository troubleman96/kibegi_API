from django.contrib import admin

from .models import ScheduleCalendar, ScheduleEvent, ScheduleSyncAccessLog


@admin.register(ScheduleCalendar)
class ScheduleCalendarAdmin(admin.ModelAdmin):
    list_display = ("name", "calendar_type", "owner", "calendar_code", "is_public_sync", "created_at")
    search_fields = ("name", "owner__email", "owner__full_name", "calendar_code")
    list_filter = ("calendar_type", "is_public_sync")
    readonly_fields = ("share_token", "calendar_code", "created_at", "updated_at")


@admin.register(ScheduleEvent)
class ScheduleEventAdmin(admin.ModelAdmin):
    list_display = ("title", "calendar", "event_type", "recurrence", "start_at", "end_at")
    list_filter = ("event_type", "recurrence", "calendar__calendar_type")
    search_fields = ("title", "calendar__name", "calendar__owner__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ScheduleSyncAccessLog)
class ScheduleSyncAccessLogAdmin(admin.ModelAdmin):
    list_display = ("calendar", "access_type", "ip_address", "accessed_at")
    list_filter = ("access_type",)
    search_fields = ("calendar__name", "calendar__owner__email", "ip_address")
    readonly_fields = ("accessed_at",)

