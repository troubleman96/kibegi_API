from rest_framework import serializers

from apps.authentication.serializers import UserSummarySerializer

from .models import Channel, ChannelBroadcast, ChannelBroadcastDelivery, ChannelMember, ChannelWallet
from .services import ChannelService


class ChannelMemberSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_phone = serializers.CharField(source='user.phone_number', read_only=True)
    invited_by_name = serializers.CharField(source='invited_by.full_name', read_only=True)
    invited_by_email = serializers.CharField(source='invited_by.email', read_only=True)

    class Meta:
        model = ChannelMember
        fields = [
            'id',
            'channel',
            'user',
            'user_name',
            'user_email',
            'user_phone',
            'role',
            'display_name',
            'email',
            'phone_number',
            'is_active',
            'joined_at',
            'left_at',
            'invited_by',
            'invited_by_name',
            'invited_by_email',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'channel', 'user', 'user_name', 'user_email', 'user_phone', 'joined_at', 'left_at', 'invited_by', 'created_at', 'updated_at']


class ChannelMemberUpsertSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=255)
    role = serializers.ChoiceField(choices=[('admin', 'Admin'), ('member', 'Member')], default='member', required=False)


class ChannelWalletSerializer(serializers.ModelSerializer):
    channel_name = serializers.CharField(source='channel.name', read_only=True)
    member_count = serializers.SerializerMethodField()
    broadcast_count = serializers.SerializerMethodField()

    class Meta:
        model = ChannelWallet
        fields = [
            'id',
            'channel',
            'channel_name',
            'balance_credits',
            'provider_name',
            'sender_id',
            'is_active',
            'last_topup_reference',
            'last_topup_at',
            'member_count',
            'broadcast_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'channel', 'created_at', 'updated_at']

    def get_member_count(self, obj):
        return obj.channel.memberships.filter(is_active=True).count()

    def get_broadcast_count(self, obj):
        return obj.channel.broadcasts.count()


class ChannelSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    member_count = serializers.SerializerMethodField()
    broadcast_count = serializers.SerializerMethodField()
    is_member = serializers.SerializerMethodField()
    my_role = serializers.SerializerMethodField()
    invite_urls = serializers.SerializerMethodField()

    class Meta:
        model = Channel
        fields = [
            'id',
            'name',
            'description',
            'visibility',
            'invite_token',
            'is_active',
            'created_by',
            'created_by_name',
            'created_by_email',
            'member_count',
            'broadcast_count',
            'is_member',
            'my_role',
            'invite_urls',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'invite_token', 'created_by', 'created_at', 'updated_at']

    def get_member_count(self, obj):
        return obj.memberships.filter(is_active=True).count()

    def get_broadcast_count(self, obj):
        return obj.broadcasts.count()

    def get_is_member(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.memberships.filter(user=request.user, is_active=True).exists()

    def get_my_role(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        membership = obj.memberships.filter(user=request.user, is_active=True).first()
        return membership.role if membership else None

    def get_invite_urls(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        return ChannelService.build_urls(request, obj)


class ChannelCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Channel
        fields = ['name', 'description', 'visibility']

    def validate_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError('Channel name is required.')
        qs = Channel.objects.filter(name__iexact=name)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A channel with this name already exists.')
        return name


class ChannelBroadcastDeliverySerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.display_name', read_only=True)

    class Meta:
        model = ChannelBroadcastDelivery
        fields = [
            'id',
            'broadcast',
            'member',
            'member_name',
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
        read_only_fields = fields


class ChannelBroadcastSerializer(serializers.ModelSerializer):
    channel_name = serializers.CharField(source='channel.name', read_only=True)
    sender_name = serializers.CharField(source='sender.full_name', read_only=True)
    sender_email = serializers.CharField(source='sender.email', read_only=True)
    delivery_count = serializers.SerializerMethodField()
    delivery_summary = serializers.SerializerMethodField()
    recent_deliveries = serializers.SerializerMethodField()

    class Meta:
        model = ChannelBroadcast
        fields = [
            'id',
            'channel',
            'channel_name',
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
        read_only_fields = ['id', 'channel', 'sender', 'status', 'recipient_count', 'sent_count', 'failed_count', 'skipped_count', 'credits_used', 'sent_at', 'created_at', 'updated_at']

    def get_delivery_count(self, obj):
        return obj.deliveries.count()

    def get_delivery_summary(self, obj):
        return {
            'sent': obj.deliveries.filter(status='sent').count(),
            'failed': obj.deliveries.filter(status='failed').count(),
            'skipped': obj.deliveries.filter(status='skipped').count(),
        }

    def get_recent_deliveries(self, obj):
        deliveries = obj.deliveries.select_related('member').order_by('-created_at')[:5]
        return ChannelBroadcastDeliverySerializer(deliveries, many=True, context=self.context).data
