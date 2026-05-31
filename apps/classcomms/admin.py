"""Admin configuration for class communications data."""

from django.contrib import admin
from django.utils.html import format_html

from .models import ClassBroadcast, ClassBroadcastDelivery, ClassCommsProfile, ClassCommsWallet, ClassContact


@admin.register(ClassCommsProfile)
class ClassCommsProfileAdmin(admin.ModelAdmin):
    list_display = ['class_name', 'public_token_short', 'public_registration_enabled', 'created_at']
    search_fields = ['class_obj__name', 'class_obj__class_code', 'public_token']
    list_filter = ['public_registration_enabled', 'created_at']
    readonly_fields = ['public_token', 'created_at', 'updated_at']
    autocomplete_fields = ['class_obj', 'created_by']

    def class_name(self, obj):
        return f'{obj.class_obj.name} ({obj.class_obj.class_code})'

    def public_token_short(self, obj):
        return f'{obj.public_token[:12]}...'


@admin.register(ClassCommsWallet)
class ClassCommsWalletAdmin(admin.ModelAdmin):
    list_display = ['class_name', 'balance_credits', 'is_active', 'provider_name', 'sender_id', 'last_topup_at']
    search_fields = ['class_obj__name', 'class_obj__class_code', 'sender_id']
    list_filter = ['is_active', 'provider_name', 'last_topup_at']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['class_obj']

    def class_name(self, obj):
        return f'{obj.class_obj.name} ({obj.class_obj.class_code})'


@admin.register(ClassContact)
class ClassContactAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'phone_number', 'class_name', 'consent_badge', 'is_active', 'consent_source', 'created_at']
    search_fields = ['full_name', 'phone_number', 'class_obj__name', 'class_obj__class_code']
    list_filter = ['consent_granted', 'is_active', 'consent_source', 'created_at']
    readonly_fields = ['created_at', 'updated_at', 'verified_at']
    autocomplete_fields = ['class_obj', 'registered_by', 'created_by']

    def class_name(self, obj):
        return f'{obj.class_obj.name} ({obj.class_obj.class_code})'

    def consent_badge(self, obj):
        color = '#10B981' if obj.consent_granted else '#EF4444'
        label = 'Consent yes' if obj.consent_granted else 'Consent no'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 8px; font-size: 11px;">{}</span>',
            color,
            label,
        )


@admin.register(ClassBroadcast)
class ClassBroadcastAdmin(admin.ModelAdmin):
    list_display = ['class_name', 'subject', 'status', 'recipient_count', 'sent_count', 'failed_count', 'skipped_count', 'credits_used', 'sent_at']
    search_fields = ['class_obj__name', 'subject', 'message']
    list_filter = ['status', 'created_at', 'sent_at']
    readonly_fields = ['recipient_count', 'sent_count', 'failed_count', 'skipped_count', 'credits_used', 'sent_at', 'created_at', 'updated_at']
    autocomplete_fields = ['class_obj', 'sender']

    def class_name(self, obj):
        return f'{obj.class_obj.name} ({obj.class_obj.class_code})'


@admin.register(ClassBroadcastDelivery)
class ClassBroadcastDeliveryAdmin(admin.ModelAdmin):
    list_display = ['broadcast_summary', 'recipient_phone', 'status', 'credits_used', 'sent_at']
    search_fields = ['recipient_phone', 'broadcast__subject', 'broadcast__class_obj__name']
    list_filter = ['status', 'provider_name', 'created_at']
    readonly_fields = ['created_at', 'updated_at', 'sent_at']
    autocomplete_fields = ['broadcast', 'contact']

    def broadcast_summary(self, obj):
        return f'{obj.broadcast.class_obj.name} - {obj.broadcast.subject or "Broadcast"}'
