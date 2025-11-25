"""
Storage App Services

This module contains business logic for managing user storage:
- Calculating storage usage from uploaded files
- Updating storage records
- Checking storage limits
- Managing storage quotas
"""
import logging
from typing import Dict, Optional
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger('kibegi')


class StorageService:
    """
    Service class for managing user storage operations.
    
    This service handles:
    - Calculating storage usage from files
    - Updating storage records
    - Checking if users can upload more files
    - Creating storage records for new users
    """
    
    # Default storage quota in megabytes
    DEFAULT_QUOTA_MB = 50.0
    
    @staticmethod
    def get_or_create_user_storage(user) -> 'UserStorage':
        """
        Get or create a storage record for a user.
        
        This method ensures every user has a storage record.
        If the record doesn't exist, it creates one with the default quota.
        
        Args:
            user: The user instance to get/create storage for
        
        Returns:
            UserStorage: The user's storage record
        """
        from .models import UserStorage
        
        # Try to get existing storage record
        storage, created = UserStorage.objects.get_or_create(
            user=user,
            defaults={
                'total_quota_mb': StorageService.DEFAULT_QUOTA_MB,
                'used_storage_bytes': 0,
            }
        )
        
        if created:
            logger.info(f"Created storage record for user {user.email} with {StorageService.DEFAULT_QUOTA_MB}MB quota")
        
        return storage
    
    @staticmethod
    def calculate_user_storage(user) -> int:
        """
        Calculate total storage used by a user from all their uploaded files.
        
        This method:
        1. Looks for files in the 'uploads' app (Upload model)
        2. Sums up the file sizes
        3. Returns total bytes used
        
        Args:
            user: The user instance to calculate storage for
        
        Returns:
            int: Total storage used in bytes
        """
        total_bytes = 0
        
        try:
            # Try to import and calculate from uploads app
            # Check if uploads app exists and has a model with file_size field
            from uploads.models import Upload
            
            # Sum all file sizes for this user
            result = Upload.objects.filter(uploader=user).aggregate(
                total=Sum('file_size')
            )
            
            if result['total']:
                total_bytes = int(result['total'])
            
            logger.debug(f"Calculated storage for {user.email}: {total_bytes} bytes")
            
        except ImportError:
            logger.warning("Uploads app not found, cannot calculate storage from uploads")
        except Exception as e:
            logger.error(f"Error calculating storage for {user.email}: {e}")
        
        # Also check files app if it exists
        try:
            from files.models import File
            
            result = File.objects.filter(uploader=user).aggregate(
                total=Sum('file_size')
            )
            
            if result['total']:
                total_bytes += int(result['total'])
                
        except ImportError:
            logger.debug("Files app not found, skipping files app storage calculation")
        except Exception as e:
            logger.error(f"Error calculating storage from files app for {user.email}: {e}")
        
        return total_bytes
    
    @staticmethod
    def update_user_storage(user, recalculate: bool = True) -> 'UserStorage':
        """
        Update a user's storage record with current usage.
        
        This method:
        1. Gets or creates the storage record
        2. Recalculates storage usage if requested
        3. Updates the storage record
        4. Saves the changes
        
        Args:
            user: The user instance to update storage for
            recalculate: Whether to recalculate storage from files (default: True)
        
        Returns:
            UserStorage: The updated storage record
        """
        from .models import UserStorage
        
        # Get or create storage record
        storage = StorageService.get_or_create_user_storage(user)
        
        # Recalculate storage if requested
        if recalculate:
            used_bytes = StorageService.calculate_user_storage(user)
            storage.used_storage_bytes = used_bytes
            storage.last_calculated = timezone.now()
            storage.save(update_fields=['used_storage_bytes', 'last_calculated', 'updated_at'])
            
            logger.info(
                f"Updated storage for {user.email}: "
                f"{storage.used_storage_mb}MB / {storage.total_quota_mb}MB "
                f"({storage.usage_percentage}%)"
            )
        
        return storage
    
    @staticmethod
    def get_storage_info(user) -> Dict:
        """
        Get comprehensive storage information for a user.
        
        This method returns a dictionary with all storage-related information
        that can be used by API endpoints or frontend.
        
        Args:
            user: The user instance to get storage info for
        
        Returns:
            dict: Dictionary containing storage information:
                - total_quota_mb: Total storage quota in MB
                - used_storage_mb: Storage used in MB
                - free_storage_mb: Free storage available in MB
                - used_storage_bytes: Storage used in bytes
                - free_storage_bytes: Free storage in bytes
                - usage_percentage: Usage as percentage (0-100)
                - is_full: Boolean indicating if storage is full
                - is_near_limit: Boolean indicating if near limit (90%)
                - last_calculated: Timestamp of last calculation
        """
        # Ensure storage record exists and is up to date
        storage = StorageService.update_user_storage(user, recalculate=True)
        
        return {
            'total_quota_mb': float(storage.total_quota_mb),
            'used_storage_mb': storage.used_storage_mb,
            'free_storage_mb': storage.free_storage_mb,
            'used_storage_bytes': storage.used_storage_bytes,
            'free_storage_bytes': storage.free_storage_bytes,
            'usage_percentage': storage.usage_percentage,
            'is_full': storage.is_full,
            'is_near_limit': storage.is_near_limit(),
            'last_calculated': storage.last_calculated.isoformat() if storage.last_calculated else None,
        }
    
    @staticmethod
    def can_upload_file(user, file_size_bytes: int):
        """
        Check if a user can upload a file of the given size.
        
        This method:
        1. Gets the user's current storage
        2. Calculates if adding this file would exceed the quota
        3. Returns whether upload is allowed and an error message if not
        
        Args:
            user: The user instance
            file_size_bytes: Size of the file to upload in bytes
        
        Returns:
            tuple: (can_upload: bool, error_message: Optional[str])
                - can_upload: True if user can upload, False otherwise
                - error_message: Error message if upload not allowed, None otherwise
        """
        # Update storage to get current usage
        storage = StorageService.update_user_storage(user, recalculate=True)
        
        # Calculate new total if file is uploaded
        new_total_bytes = storage.used_storage_bytes + file_size_bytes
        quota_bytes = int(storage.total_quota_mb * 1024 * 1024)
        
        # Check if upload would exceed quota
        if new_total_bytes > quota_bytes:
            free_mb = storage.free_storage_mb
            needed_mb = round(file_size_bytes / (1024 * 1024), 2)
            
            return False, (
                f"Insufficient storage space. "
                f"You have {free_mb}MB free, but need {needed_mb}MB. "
                f"Please delete some files to free up space."
            )
        
        return True, None
    
    @staticmethod
    def increase_storage_quota(user, additional_mb: float) -> 'UserStorage':
        """
        Increase a user's storage quota.
        
        This method adds additional storage quota to a user's account.
        Useful for premium users or special promotions.
        
        Args:
            user: The user instance
            additional_mb: Additional storage quota in megabytes
        
        Returns:
            UserStorage: The updated storage record
        """
        from .models import UserStorage
        
        storage = StorageService.get_or_create_user_storage(user)
        storage.total_quota_mb += additional_mb
        storage.save(update_fields=['total_quota_mb', 'updated_at'])
        
        logger.info(
            f"Increased storage quota for {user.email} by {additional_mb}MB. "
            f"New quota: {storage.total_quota_mb}MB"
        )
        
        return storage
    
    @staticmethod
    def set_storage_quota(user, quota_mb: float) -> 'UserStorage':
        """
        Set a user's storage quota to a specific value.
        
        Args:
            user: The user instance
            quota_mb: New storage quota in megabytes
        
        Returns:
            UserStorage: The updated storage record
        """
        from .models import UserStorage
        
        storage = StorageService.get_or_create_user_storage(user)
        storage.total_quota_mb = quota_mb
        storage.save(update_fields=['total_quota_mb', 'updated_at'])
        
        logger.info(f"Set storage quota for {user.email} to {quota_mb}MB")
        
        return storage

