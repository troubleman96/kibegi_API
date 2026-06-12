from django.contrib import admin

from .models import Channel, ChannelMember, ChannelWallet, ChannelBroadcast, ChannelBroadcastDelivery


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ['name', 'visibility', 'is_active', 'created_by', 'created_at']
    list_filter = ['visibility', 'is_active', 'created_at']
    search_fields = ['name', 'description']


@admin.register(ChannelMember)
class ChannelMemberAdmin(admin.ModelAdmin):
    list_display = ['channel', 'display_name', 'role', 'is_active', 'joined_at']
    list_filter = ['role', 'is_active', 'joined_at']
    search_fields = ['display_name', 'email', 'phone_number', 'channel__name']
    autocomplete_fields = ['channel', 'user', 'invited_by']


@admin.register(ChannelWallet)
class ChannelWalletAdmin(admin.ModelAdmin):
    list_display = ['channel', 'balance_credits', 'is_active', 'provider_name', 'sender_id']
    search_fields = ['channel__name', 'sender_id']
    list_filter = ['is_active', 'provider_name']


@admin.register(ChannelBroadcast)
class ChannelBroadcastAdmin(admin.ModelAdmin):
    list_display = ['channel', 'subject', 'status', 'recipient_count', 'sent_count', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['subject', 'message', 'channel__name']
    autocomplete_fields = ['channel', 'sender']


@admin.register(ChannelBroadcastDelivery)
class ChannelBroadcastDeliveryAdmin(admin.ModelAdmin):
    list_display = ['broadcast', 'recipient_phone', 'status', 'credits_used', 'sent_at']
    list_filter = ['status', 'sent_at']
    search_fields = ['recipient_phone', 'broadcast__subject', 'broadcast__channel__name']
    autocomplete_fields = ['broadcast', 'member']

