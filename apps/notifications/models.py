from django.db import models
from django.conf import settings


class Notification(models.Model):
    """
    Notification model for user notifications.
    
    Supports different notification types:
    - share_request: When someone shares a file with you
    - friend_request: When someone sends you a friend request
    - file_shared: When a shared file is accepted/available
    
    Fields:
        user: Recipient of the notification
        notification_type: Type of notification (share_request, friend_request, file_shared)
        content: Human-readable notification message
        related_object_id: ID of related object (share ID, friendship ID, etc.)
        is_read: Whether notification has been read
        created_at: When notification was created
    
    Example:
        Notification.objects.create(
            user=recipient_user,
            notification_type='share_request',
            content='John Doe shared a file with you',
            related_object_id='123'
        )
    """
    
    TYPE_CHOICES = [
        ('share_request', 'Share Request'),
        ('share_accepted', 'Share Accepted'),
        ('share_rejected', 'Share Rejected'),
        ('friend_request', 'Friend Request'),
        ('friend_accepted', 'Friend Accepted'),
        ('upload_created', 'Upload Created'),
        ('class_joined', 'Class Joined'),
        # Backward-compatible / legacy type kept for older clients.
        ('file_shared', 'File Shared'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        help_text="User who will receive this notification"
    )
    notification_type = models.CharField(
        max_length=30,
        choices=TYPE_CHOICES,
        help_text="Type of notification"
    )
    content = models.TextField(
        help_text="Human-readable notification message"
    )
    related_object_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="ID of related object (share ID, friendship ID, etc.)"
    )
    is_read = models.BooleanField(
        default=False,
        help_text="Whether notification has been read"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When notification was created"
    )
    
    class Meta:
        ordering = ['-created_at']  # Most recent first
        indexes = [
            models.Index(fields=['user', 'is_read']),  # For filtering unread notifications
            models.Index(fields=['user', '-created_at']),  # For user's notification list
        ]
    
    def __str__(self):
        """String representation"""
        status = "Read" if self.is_read else "Unread"
        return f"{self.user.email} - {self.notification_type} - {status}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])
