import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class SharedFile(models.Model):
    """
    Model for tracking file sharing between users.
    
    Allows users to share uploaded files with other users.
    Implements a request/accept flow where the recipient must accept the share.
    
    Relationships:
    - upload: The file being shared (from uploads app)
    - shared_by: User who is sharing the file
    - shared_with: User receiving the file share
    
    Status Flow:
    1. 'pending' - Share request sent, awaiting recipient action
    2. 'accepted' - Recipient accepted, can now access file
    3. 'rejected' - Recipient declined the share
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the share"
    )
    upload = models.ForeignKey(
        'uploads.Upload',  # Reference to Upload model in uploads app
        on_delete=models.CASCADE,  # Delete share if file is deleted
        related_name='shares',  # Access shares via upload.shares.all()
        help_text="The file being shared"
    )
    shared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # User who owns/shares the file
        on_delete=models.CASCADE,  # Delete share if sharer is deleted
        related_name='shared_files',  # Access via user.shared_files.all()
        help_text="User who is sharing the file"
    )
    shared_with = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # User receiving the file
        on_delete=models.CASCADE,  # Delete share if recipient is deleted
        related_name='received_files',  # Access via user.received_files.all()
        help_text="User receiving the file share"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text="Current status of the share request"
    )
    message = models.TextField(
        blank=True,
        max_length=500,
        help_text="Optional message from sharer to recipient"
    )
    shared_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the share request was created"
    )
    accepted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the share was accepted (null if pending/rejected)"
    )
    rejected_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the share was rejected (null if pending/accepted)"
    )
    
    class Meta:
        # Prevent duplicate shares of same file to same user
        unique_together = ['upload', 'shared_with']
        ordering = ['-shared_at']  # Newest shares first
        verbose_name = "Shared File"
        verbose_name_plural = "Shared Files"
        indexes = [
            # Index for querying shares by status
            models.Index(fields=['status', 'shared_at']),
            # Index for querying user's received shares
            models.Index(fields=['shared_with', 'status']),
        ]
    
    def __str__(self):
        return f"{self.upload.file_name} shared by {self.shared_by.full_name} with {self.shared_with.full_name}"
    
    def accept(self):
        """
        Accept the share request.
        Updates status to 'accepted' and records acceptance timestamp.
        """
        previous_status = self.status
        if previous_status == 'accepted':
            return

        self.status = 'accepted'
        self.accepted_at = timezone.now()
        self.rejected_at = None  # Clear any previous rejection
        self.save(update_fields=['status', 'accepted_at', 'rejected_at'])

        if previous_status == 'pending':
            try:
                from apps.notifications.services import NotificationService

                recipient_name = getattr(self.shared_with, "full_name", "Someone")
                file_name = getattr(self.upload, "file_name", "a file")
                content = f"{recipient_name} accepted your share for \"{file_name}\""
                NotificationService.create_notification(
                    user=self.shared_by,
                    notification_type="share_accepted",
                    content=content,
                    related_id=str(self.id),
                )
            except Exception:
                pass
    
    def reject(self):
        """
        Reject the share request.
        Updates status to 'rejected' and records rejection timestamp.
        """
        previous_status = self.status
        if previous_status == 'rejected':
            return

        self.status = 'rejected'
        self.rejected_at = timezone.now()
        self.accepted_at = None  # Clear any previous acceptance
        self.save(update_fields=['status', 'rejected_at', 'accepted_at'])

        if previous_status == 'pending':
            try:
                from apps.notifications.services import NotificationService

                recipient_name = getattr(self.shared_with, "full_name", "Someone")
                file_name = getattr(self.upload, "file_name", "a file")
                content = f"{recipient_name} rejected your share for \"{file_name}\""
                NotificationService.create_notification(
                    user=self.shared_by,
                    notification_type="share_rejected",
                    content=content,
                    related_id=str(self.id),
                )
            except Exception:
                pass
    
    def is_pending(self):
        """Check if share is awaiting acceptance"""
        return self.status == 'pending'
    
    def is_accepted(self):
        """Check if share has been accepted"""
        return self.status == 'accepted'
    
    def is_rejected(self):
        """Check if share has been rejected"""
        return self.status == 'rejected'
    
    @property
    def can_access_file(self):
        """
        Check if recipient can access the shared file.
        Only accepted shares grant access, and file must not be deleted.
        """
        return self.is_accepted() and not self.upload.is_deleted
