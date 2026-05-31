from rest_framework import serializers

from apps.authentication.serializers import UserSummarySerializer
from apps.classes.models import Class

from .models import ClassBroadcast, ClassBroadcastDelivery, ClassCommsProfile, ClassCommsWallet, ClassContact
from .services import ClassCommsService


class ClassCommsProfileSerializer(serializers.ModelSerializer):
    """Serializer for class-level public registration settings."""

    class_name = serializers.CharField(source='class_obj.name', read_only=True)
    class_code = serializers.CharField(source='class_obj.class_code', read_only=True)
    contact_count = serializers.SerializerMethodField()
    broadcast_count = serializers.SerializerMethodField()
    registration_urls = serializers.SerializerMethodField()

    class Meta:
        model = ClassCommsProfile
        fields = [
            'id',
            'class_obj',
            'class_name',
            'class_code',
            'public_token',
            'public_registration_enabled',
            'default_sender_name',
            'registration_hint',
            'contact_count',
            'broadcast_count',
            'registration_urls',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'class_obj', 'public_token', 'created_at', 'updated_at']

    def get_contact_count(self, obj):
        return obj.class_obj.comms_contacts.filter(is_active=True).count()

    def get_broadcast_count(self, obj):
        return obj.class_obj.comms_broadcasts.count()

    def get_registration_urls(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        return ClassCommsService.build_registration_urls(request, obj.class_obj)


class ClassCommsWalletSerializer(serializers.ModelSerializer):
    """Serializer for class SMS credit wallets."""

    class_name = serializers.CharField(source='class_obj.name', read_only=True)
    contact_count = serializers.SerializerMethodField()
    broadcast_count = serializers.SerializerMethodField()

    class Meta:
        model = ClassCommsWallet
        fields = [
            'id',
            'class_obj',
            'class_name',
            'balance_credits',
            'provider_name',
            'sender_id',
            'is_active',
            'last_topup_reference',
            'last_topup_at',
            'contact_count',
            'broadcast_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'class_obj', 'created_at', 'updated_at']

    def get_contact_count(self, obj):
        return obj.class_obj.comms_contacts.filter(is_active=True).count()

    def get_broadcast_count(self, obj):
        return obj.class_obj.comms_broadcasts.count()


class ClassContactSerializer(serializers.ModelSerializer):
    """Serializer for class contact records."""

    class_name = serializers.CharField(source='class_obj.name', read_only=True)
    added_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    added_by_email = serializers.CharField(source='created_by.email', read_only=True)
    registered_by_name = serializers.CharField(source='registered_by.full_name', read_only=True)
    user_profile_image_url = serializers.SerializerMethodField()

    class Meta:
        model = ClassContact
        fields = [
            'id',
            'class_obj',
            'class_name',
            'full_name',
            'phone_number',
            'consent_granted',
            'consent_source',
            'notes',
            'is_active',
            'registered_by',
            'registered_by_name',
            'created_by',
            'added_by_name',
            'added_by_email',
            'verified_at',
            'user_profile_image_url',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'class_obj', 'registered_by', 'created_by', 'verified_at', 'created_at', 'updated_at']

    def get_user_profile_image_url(self, obj):
        if obj.registered_by:
            return UserSummarySerializer(context=self.context).get_profile_image_url(obj.registered_by)
        return None


class ClassContactUpsertSerializer(serializers.Serializer):
    """Input serializer for manual and public contact registration."""

    full_name = serializers.CharField(max_length=255)
    phone_number = serializers.CharField(max_length=32)
    consent_granted = serializers.BooleanField(default=True)
    notes = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_phone_number(self, value):
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError('Phone number is required.')
        return cleaned


class ClassRepresentativeSerializer(serializers.Serializer):
    """Promote or demote a class member to representative."""

    user_id = serializers.IntegerField()
    role = serializers.ChoiceField(choices=[('representative', 'Representative'), ('student', 'Student')])


class ClassBroadcastDeliverySerializer(serializers.ModelSerializer):
    """Read-only serializer for per-recipient broadcast results."""

    contact_name = serializers.CharField(source='contact.full_name', read_only=True)

    class Meta:
        model = ClassBroadcastDelivery
        fields = [
            'id',
            'broadcast',
            'contact',
            'contact_name',
            'recipient_phone',
            'provider_name',
            'provider_message_id',
            'status',
            'message',
            'credits_used',
            'error_message',
            'provider_response',
            'sent_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'broadcast',
            'contact',
            'contact_name',
            'recipient_phone',
            'provider_name',
            'provider_message_id',
            'status',
            'message',
            'credits_used',
            'error_message',
            'provider_response',
            'sent_at',
            'created_at',
            'updated_at',
        ]


class ClassBroadcastSerializer(serializers.ModelSerializer):
    """Serializer for class-wide SMS broadcasts."""

    class_name = serializers.CharField(source='class_obj.name', read_only=True)
    sender_name = serializers.CharField(source='sender.full_name', read_only=True)
    sender_email = serializers.CharField(source='sender.email', read_only=True)
    delivery_count = serializers.SerializerMethodField()
    delivery_summary = serializers.SerializerMethodField()
    recent_deliveries = serializers.SerializerMethodField()

    class Meta:
        model = ClassBroadcast
        fields = [
            'id',
            'class_obj',
            'class_name',
            'sender',
            'sender_name',
            'sender_email',
            'subject',
            'message',
            'venue',
            'status',
            'recipient_count',
            'sent_count',
            'failed_count',
            'skipped_count',
            'credits_used',
            'delivery_count',
            'delivery_summary',
            'recent_deliveries',
            'sent_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'class_obj',
            'sender',
            'status',
            'recipient_count',
            'sent_count',
            'failed_count',
            'skipped_count',
            'credits_used',
            'sent_at',
            'created_at',
            'updated_at',
        ]

    def get_delivery_count(self, obj):
        return obj.deliveries.count()

    def get_delivery_summary(self, obj):
        return {
            'sent': obj.deliveries.filter(status='sent').count(),
            'failed': obj.deliveries.filter(status='failed').count(),
            'skipped': obj.deliveries.filter(status='skipped').count(),
        }

    def get_recent_deliveries(self, obj):
        deliveries = obj.deliveries.select_related('contact').order_by('-created_at')[:5]
        return ClassBroadcastDeliverySerializer(deliveries, many=True, context=self.context).data
