from rest_framework import serializers
from .models import SmsAccount, SmsDelivery


class SmsAccountSerializer(serializers.ModelSerializer):
    owner_type = serializers.CharField(source='owner_content_type.model', read_only=True)

    class Meta:
        model = SmsAccount
        fields = ['id', 'owner_type', 'owner_object_id', 'phone_number', 'balance_credits', 'provider_name', 'sender_id', 'is_active']


class SmsDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = SmsDelivery
        fields = ['id', 'recipient_phone', 'status', 'provider_message_id', 'message', 'credits_used', 'error_message', 'sent_at', 'created_at']
