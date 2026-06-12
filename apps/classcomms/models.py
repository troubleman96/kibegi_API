import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


def generate_public_token():
    """Generate a stable public token for registration links."""
    return secrets.token_urlsafe(32)


class ClassCommsProfile(models.Model):
    """Per-class configuration for public registration and messaging."""

    class_obj = models.OneToOneField(
        'classes.Class',
        on_delete=models.CASCADE,
        related_name='comms_profile',
    )
    public_token = models.CharField(max_length=255, unique=True, default=generate_public_token)
    public_registration_enabled = models.BooleanField(default=True)
    default_sender_name = models.CharField(max_length=80, blank=True, default='')
    registration_hint = models.CharField(
        max_length=255,
        blank=True,
        default='Register your name and phone number to receive class updates.',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_class_comms_profiles',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['class_obj__name']

    def __str__(self):
        return f"Comms profile for {self.class_obj.name}"

    def reset_public_token(self):
        """Rotate the public token when the link should be invalidated."""
        self.public_token = generate_public_token()
        self.save(update_fields=['public_token', 'updated_at'])


class ClassCommsWallet(models.Model):
    """Credits wallet used to pay for SMS broadcasts from a class."""

    class_obj = models.OneToOneField(
        'classes.Class',
        on_delete=models.CASCADE,
        related_name='comms_wallet',
    )
    balance_credits = models.PositiveIntegerField(default=0)
    provider_name = models.CharField(max_length=40, default='africastalking')
    sender_id = models.CharField(max_length=40, blank=True, default='')
    is_active = models.BooleanField(default=True)
    last_topup_reference = models.CharField(max_length=120, blank=True, default='')
    last_topup_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['class_obj__name']

    def __str__(self):
        return f"SMS wallet for {self.class_obj.name}"


class ClassContact(models.Model):
    """A registered contact that can receive class SMS broadcasts."""

    SOURCE_MANUAL = 'manual'
    SOURCE_PUBLIC = 'public'
    SOURCE_IMPORTED = 'imported'
    SOURCE_CHOICES = (
        (SOURCE_MANUAL, 'Manual'),
        (SOURCE_PUBLIC, 'Public registration'),
        (SOURCE_IMPORTED, 'Imported'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    class_obj = models.ForeignKey('classes.Class', on_delete=models.CASCADE, related_name='comms_contacts')
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='class_comms_contacts',
    )
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=32)
    consent_granted = models.BooleanField(default=True)
    consent_source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='class_comms_registered_contacts',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='class_comms_created_contacts',
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['full_name', 'created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['class_obj', 'phone_number'],
                name='unique_class_contact_phone_per_class',
            )
        ]
        indexes = [
            models.Index(fields=['class_obj', 'is_active']),
            models.Index(fields=['class_obj', 'phone_number']),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.phone_number})"

    def save(self, *args, **kwargs):
        self.phone_number = self.phone_number.strip()
        super().save(*args, **kwargs)


class ClassBroadcast(models.Model):
    """A class-wide SMS broadcast created by a lecturer or representative."""

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
    class_obj = models.ForeignKey('classes.Class', on_delete=models.CASCADE, related_name='comms_broadcasts')
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='class_comms_broadcasts',
    )
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
            models.Index(fields=['class_obj', 'status']),
            models.Index(fields=['class_obj', '-created_at']),
        ]

    def __str__(self):
        created_at = self.created_at or timezone.now()
        return f"{self.class_obj.name} broadcast @ {timezone.localtime(created_at)}"


class ClassBroadcastDelivery(models.Model):
    """Delivery log for one SMS broadcast recipient."""

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
    broadcast = models.ForeignKey(ClassBroadcast, on_delete=models.CASCADE, related_name='deliveries')
    contact = models.ForeignKey(ClassContact, on_delete=models.SET_NULL, null=True, blank=True, related_name='broadcast_deliveries')
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
        constraints = [
            models.UniqueConstraint(
                fields=['broadcast', 'contact'],
                name='unique_broadcast_delivery_per_contact',
            )
        ]
        indexes = [
            models.Index(fields=['broadcast', 'status']),
            models.Index(fields=['broadcast', 'recipient_phone']),
        ]

    def __str__(self):
        return f"{self.broadcast.class_obj.name} -> {self.recipient_phone} ({self.status})"
