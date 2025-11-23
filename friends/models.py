from django.db import models
from django.conf import settings
from django.utils import timezone


class Friendship(models.Model):
    """
    Friendship model for managing friend relationships.
    
    Implements a request/accept pattern where:
    1. User A sends friend request to User B (status=pending)
    2. User B accepts request (status=accepted)
    3. Both users become friends
    
    Fields:
    - user: The user who initiated the friendship
    - friend: The user who received the request
    - nickname: Optional custom name for the friend
    - status: pending or accepted
    - created_at: When friendship was created
    - accepted_at: When friendship was accepted (null if pending)
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='friendships',
        help_text="User who sent the friend request"
    )
    friend = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='friend_of',
        help_text="User who received the friend request"
    )
    nickname = models.CharField(
        max_length=100,
        blank=True,
        help_text="Custom nickname for the friend"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        help_text="Status of the friendship (pending or accepted)"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the friend request was sent"
    )
    accepted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the friend request was accepted"
    )
    
    class Meta:
        unique_together = ['user', 'friend']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['friend', 'status']),
        ]
    
    def __str__(self):
        return f"{self.user.email} -> {self.friend.email} ({self.status})"
    
    def accept(self):
        """
        Accept a pending friend request.
        
        Changes status from pending to accepted and sets accepted_at timestamp.
        """
        if self.status == 'pending':
            self.status = 'accepted'
            self.accepted_at = timezone.now()
            self.save()
    
    def is_pending(self):
        """Check if friendship is still pending"""
        return self.status == 'pending'
    
    def is_accepted(self):
        """Check if friendship is accepted"""
        return self.status == 'accepted'
    
    @property
    def display_name(self):
        """Get display name (nickname if set, otherwise friend's full name)"""
        return self.nickname if self.nickname else self.friend.full_name
