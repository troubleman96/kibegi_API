from django.contrib import admin
from .models import SmsAccount, SmsDelivery


@admin.register(SmsAccount)
class SmsAccountAdmin(admin.ModelAdmin):
    list_display = ['owner', 'phone_number', 'balance_credits', 'is_active', 'provider_name', 'sender_id']
    search_fields = ['owner_object_id', 'phone_number']
    list_filter = ['is_active', 'provider_name']


@admin.register(SmsDelivery)
class SmsDeliveryAdmin(admin.ModelAdmin):
    list_display = ['recipient_phone', 'status', 'sms_account', 'sent_at']
    search_fields = ['recipient_phone', 'provider_message_id']
    list_filter = ['status', 'provider_name']
    readonly_fields = ['created_at', 'updated_at', 'sent_at']
