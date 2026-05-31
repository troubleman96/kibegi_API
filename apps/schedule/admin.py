from django.contrib import admin

from .models import ScheduleCalendar, ScheduleEvent, ScheduleSmsAccount, ScheduleSmsDeliveryLog, ScheduleSyncAccessLog


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


@admin.register(ScheduleSmsAccount)
class ScheduleSmsAccountAdmin(admin.ModelAdmin):
    list_display = ("owner", "phone_number", "balance_credits", "provider_name", "is_active", "last_topup_at")
    search_fields = ("owner__email", "owner__full_name", "phone_number")
    list_filter = ("provider_name", "is_active")


@admin.register(ScheduleSmsDeliveryLog)
class ScheduleSmsDeliveryLogAdmin(admin.ModelAdmin):
    list_display = ("event", "recipient_phone", "status", "credits_used", "provider_name", "sent_at")
    search_fields = ("event__title", "recipient_phone", "provider_message_id")
    list_filter = ("status", "provider_name")
    readonly_fields = ("created_at", "updated_at", "sent_at")

