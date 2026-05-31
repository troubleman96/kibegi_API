import uuid
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone


class SmsAccount(models.Model):
    """Generic SMS wallet that can be attached to users, classes, or other owners.

    Uses a GenericForeignKey so a single table stores wallets for both user-owned
    wallets (schedule reminders) and class-owned wallets (class broadcasts).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    owner_object_id = models.CharField(max_length=255)
    owner = GenericForeignKey('owner_content_type', 'owner_object_id')

    phone_number = models.CharField(max_length=32, blank=True, default='')
    balance_credits = models.PositiveIntegerField(default=0)
    provider_name = models.CharField(max_length=40, default='africastalking')
    sender_id = models.CharField(max_length=40, blank=True, default='')
    is_active = models.BooleanField(default=True)
    last_topup_reference = models.CharField(max_length=120, blank=True, default='')
    last_topup_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('owner_content_type', 'owner_object_id')]
        ordering = ['-created_at']

    def __str__(self):
        return f"SMS wallet for {self.owner}" if self.owner else f"SMS wallet {self.id}"


class SmsDelivery(models.Model):
    """Delivery record for a sent SMS tied to a generic context object (event, broadcast, etc)."""

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
    context_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name='sms_deliveries')
    context_object_id = models.CharField(max_length=255)
    context_object = GenericForeignKey('context_content_type', 'context_object_id')

    sms_account = models.ForeignKey('SmsAccount', on_delete=models.SET_NULL, null=True, blank=True, related_name='deliveries')
    recipient_phone = models.CharField(max_length=32, blank=True, default='')
    provider_name = models.CharField(max_length=40, default='africastalking')
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
        indexes = [
            models.Index(fields=['context_content_type', 'context_object_id']),
            models.Index(fields=['sms_account', 'status']),
        ]

    def __str__(self):
        return f"SMS to {self.recipient_phone} ({self.status})"
