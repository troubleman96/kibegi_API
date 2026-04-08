"""
Storage App Models

This module defines the data models for tracking user storage usage.
Each user gets a default storage quota (50MB) that can be tracked and managed.
"""
from django.db import models
from django.core.validators import MinValueValidator
from django.conf import settings


class UserStorage(models.Model):
    """
    Model to track storage usage for each user.
    
    This model stores:
    - Total storage quota allocated to the user (default: 50MB)
    - Current storage used (calculated from uploaded files)
    - Timestamps for tracking when storage was last updated
    
    Attributes:
        user: One-to-one relationship with the User model
        total_quota_mb: Total storage quota in megabytes (default: 50MB)
        used_storage_bytes: Current storage used in bytes (calculated)
        last_calculated: Timestamp of last storage calculation
    """
    
    # One-to-one relationship: Each user has exactly one storage record
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='storage',
        help_text="The user this storage record belongs to"
    )
    
    # Total storage quota in megabytes (default: 50MB)
    # This is the maximum storage the user can use
    total_quota_mb = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=50.00,
        validators=[MinValueValidator(0)],
        help_text="Total storage quota in megabytes (default: 50MB)"
    )
    
    # Current storage used in bytes
    # This will be calculated from all user's uploaded files
    used_storage_bytes = models.BigIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Current storage used in bytes (calculated from uploaded files)"
    )
    
    # Timestamp tracking
    created_at = models.DateTimeField(auto_now_add=True, help_text="When this storage record was created")
    updated_at = models.DateTimeField(auto_now=True, help_text="When this storage record was last updated")
    last_calculated = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp of last storage calculation"
    )
    
    class Meta:
        verbose_name = "User Storage"
        verbose_name_plural = "User Storage Records"
        ordering = ['-updated_at']
    
    def __str__(self):
        """String representation of the storage record"""
        return f"{self.user.email} - {self.used_storage_mb:.2f}MB / {self.total_quota_mb}MB"
    
    @property
    def used_storage_mb(self):
        """
        Convert used storage from bytes to megabytes.
        
        Returns:
            float: Storage used in megabytes (rounded to 2 decimal places)
        """
        return round(self.used_storage_bytes / (1024 * 1024), 2)
    
    @property
    def free_storage_mb(self):
        """
        Calculate free storage available to the user.
        
        Returns:
            float: Free storage in megabytes (rounded to 2 decimal places)
        """
        free = float(self.total_quota_mb) - self.used_storage_mb
        return round(max(0, free), 2)  # Ensure it's not negative
    
    @property
    def free_storage_bytes(self):
        """
        Calculate free storage in bytes.
        
        Returns:
            int: Free storage in bytes
        """
        return max(0, (int(self.total_quota_mb * 1024 * 1024) - self.used_storage_bytes))
    
    @property
    def usage_percentage(self):
        """
        Calculate storage usage as a percentage.
        
        Returns:
            float: Usage percentage (0-100, rounded to 2 decimal places)
        """
        if self.total_quota_mb == 0:
            return 0.0
        percentage = (self.used_storage_mb / float(self.total_quota_mb)) * 100
        return round(min(100, max(0, percentage)), 2)  # Clamp between 0 and 100
    
    @property
    def is_full(self):
        """
        Check if user has reached their storage limit.
        
        Returns:
            bool: True if storage is full (or over limit), False otherwise
        """
        return self.used_storage_bytes >= int(self.total_quota_mb * 1024 * 1024)
    
    def is_near_limit(self, threshold_percentage=90):
        """
        Check if user is near their storage limit.
        
        Args:
            threshold_percentage: Percentage threshold (default: 90%)
        
        Returns:
            bool: True if usage is above threshold, False otherwise
        """
        return self.usage_percentage >= threshold_percentage


class StorageUsageHistory(models.Model):
    """
    Model to track storage usage history over time.
    
    This model stores historical snapshots of storage usage,
    useful for analytics and tracking storage growth patterns.
    
    Attributes:
        user_storage: Foreign key to UserStorage
        used_storage_bytes: Storage used at this point in time
        recorded_at: When this snapshot was recorded
    """
    
    user_storage = models.ForeignKey(
        UserStorage,
        on_delete=models.CASCADE,
        related_name='usage_history',
        help_text="The storage record this history entry belongs to"
    )
    
    # Storage used at this point in time (in bytes)
    used_storage_bytes = models.BigIntegerField(
        validators=[MinValueValidator(0)],
        help_text="Storage used in bytes at this point in time"
    )
    
    # When this snapshot was recorded
    recorded_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this storage snapshot was recorded"
    )
    
    class Meta:
        verbose_name = "Storage Usage History"
        verbose_name_plural = "Storage Usage History"
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['user_storage', '-recorded_at']),
        ]
    
    def __str__(self):
        """String representation of the history record"""
        used_mb = round(self.used_storage_bytes / (1024 * 1024), 2)
        return f"{self.user_storage.user.email} - {used_mb}MB at {self.recorded_at}"
