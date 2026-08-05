import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


def generate_invite_token():
    return secrets.token_urlsafe(32)


class Channel(models.Model):
    VISIBILITY_PUBLIC = 'public'
    VISIBILITY_PRIVATE = 'private'
    VISIBILITY_CHOICES = (
        (VISIBILITY_PUBLIC, 'Public'),
        (VISIBILITY_PRIVATE, 'Private'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True, default='')
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default=VISIBILITY_PUBLIC, db_index=True)
    invite_token = models.CharField(max_length=255, unique=True, default=generate_invite_token)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_channels',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ChannelMember(models.Model):
    ROLE_OWNER = 'owner'
    ROLE_ADMIN = 'admin'
    ROLE_MEMBER = 'member'
    ROLE_CHOICES = (
        (ROLE_OWNER, 'Owner'),
        (ROLE_ADMIN, 'Admin'),
        (ROLE_MEMBER, 'Member'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='channel_memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    display_name = models.CharField(max_length=255, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    phone_number = models.CharField(max_length=32, blank=True, default='')
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(default=timezone.now)
    left_at = models.DateTimeField(null=True, blank=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='channel_members_invited',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['channel__name', 'display_name', 'created_at']
        constraints = [
            models.UniqueConstraint(fields=['channel', 'user'], name='unique_channel_member'),
        ]
        indexes = [
            models.Index(fields=['channel', 'is_active']),
            models.Index(fields=['channel', 'role']),
        ]

    def __str__(self):
        return f'{self.display_name or self.user.full_name} in {self.channel.name}'

    def save(self, *args, **kwargs):
        if self.user_id:
            self.display_name = self.display_name.strip() or getattr(self.user, 'full_name', '') or self.display_name
            self.email = self.email.strip() or getattr(self.user, 'email', '') or self.email
            self.phone_number = self.phone_number.strip() or getattr(self.user, 'phone_number', '') or self.phone_number
        super().save(*args, **kwargs)


class ChannelWallet(models.Model):
    channel = models.OneToOneField(Channel, on_delete=models.CASCADE, related_name='wallet')
    api_key = models.CharField(max_length=200, blank=True, default='')
    balance_credits = models.PositiveIntegerField(default=0)
    provider_name = models.CharField(max_length=40, default='sendafrica')
    sender_id = models.CharField(max_length=40, blank=True, default='')
    is_active = models.BooleanField(default=True)
    last_topup_reference = models.CharField(max_length=120, blank=True, default='')
    last_topup_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['channel__name']

    def __str__(self):
        return f'Channel wallet for {self.channel.name}'


class ChannelBroadcast(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_SENDING = 'sending'
    STATUS_SENT = 'sent'
    STATUS_PARTIAL = 'partial'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = (
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SENDING, 'Sending'),
        (STATUS_SENT, 'Sent'),
        (STATUS_PARTIAL, 'Partially sent'),
        (STATUS_FAILED, 'Failed'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='broadcasts')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='channel_broadcasts')
    subject = models.CharField(max_length=200, blank=True, default='')
    message = models.TextField()
    venue = models.CharField(max_length=255, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
    recipient_count = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    credits_used = models.PositiveIntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['channel', 'status']),
            models.Index(fields=['channel', '-created_at']),
        ]

    def __str__(self):
        created_at = self.created_at or timezone.now()
        return f"{self.channel.name} broadcast @ {timezone.localtime(created_at)}"


class ChannelBroadcastDelivery(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_SENT = 'sent'
    STATUS_FAILED = 'failed'
    STATUS_SKIPPED = 'skipped'
    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending'),
        (STATUS_SENT, 'Sent'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_SKIPPED, 'Skipped'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    broadcast = models.ForeignKey(ChannelBroadcast, on_delete=models.CASCADE, related_name='deliveries')
    member = models.ForeignKey(ChannelMember, on_delete=models.SET_NULL, null=True, blank=True, related_name='broadcast_deliveries')
    recipient_phone = models.CharField(max_length=32, blank=True, default='')
    provider_name = models.CharField(max_length=40, default='sendafrica')
    provider_message_id = models.CharField(max_length=120, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    message = models.TextField()
    credits_used = models.PositiveIntegerField(default=1)
    error_message = models.TextField(blank=True, default='')
    provider_response = models.JSONField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['broadcast', 'member'], name='unique_channel_broadcast_delivery_per_member'),
        ]
        indexes = [
            models.Index(fields=['broadcast', 'status']),
            models.Index(fields=['broadcast', 'recipient_phone']),
        ]

    def __str__(self):
        return f"{self.broadcast.channel.name} -> {self.recipient_phone} ({self.status})"

