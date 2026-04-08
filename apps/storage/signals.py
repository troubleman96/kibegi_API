"""
Storage App Signals

This module defines Django signals to automatically manage storage:
- Create storage record when user is created
- Update storage when files are uploaded/deleted
"""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings

logger = logging.getLogger('kibegi')


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_storage(sender, instance, created, **kwargs):
    """
    Signal handler: Create storage record when a new user is created.
    
    This signal automatically creates a UserStorage record with default
    50MB quota when a new user registers.
    
    Args:
        sender: The model class (User)
        instance: The user instance that was saved
        created: Boolean indicating if this is a new user
        **kwargs: Additional signal arguments
    """
    if created:
        # Import here to avoid circular imports
        from .services import StorageService
        
        try:
            # Create storage record with default quota
            storage = StorageService.get_or_create_user_storage(instance)
            logger.info(f"Created storage record for new user: {instance.email}")
        except Exception as e:
            logger.error(f"Failed to create storage record for {instance.email}: {e}")


@receiver(post_save, sender='uploads.Upload')
def update_storage_on_upload(sender, instance, created, **kwargs):
    """
    Signal handler: Update storage when a file is uploaded.
    
    This signal automatically updates the user's storage usage
    when a new file is uploaded via the uploads app.
    
    Args:
        sender: The model class (Upload)
        instance: The upload instance that was saved
        created: Boolean indicating if this is a new upload
        **kwargs: Additional signal arguments
    """
    if created and hasattr(instance, 'uploader') and hasattr(instance, 'file_size'):
        # Import here to avoid circular imports
        from .services import StorageService
        
        try:
            # Update storage for the user
            StorageService.update_user_storage(instance.uploader, recalculate=True)
            logger.debug(f"Updated storage for user {instance.uploader.email} after upload")
        except Exception as e:
            logger.error(f"Failed to update storage after upload: {e}")


@receiver(post_delete, sender='uploads.Upload')
def update_storage_on_delete(sender, instance, **kwargs):
    """
    Signal handler: Update storage when a file is deleted.
    
    This signal automatically updates the user's storage usage
    when a file is deleted from the uploads app.
    
    Args:
        sender: The model class (Upload)
        instance: The upload instance that was deleted
        **kwargs: Additional signal arguments
    """
    if hasattr(instance, 'uploader'):
        # Import here to avoid circular imports
        from .services import StorageService
        
        try:
            # Update storage for the user
            StorageService.update_user_storage(instance.uploader, recalculate=True)
            logger.debug(f"Updated storage for user {instance.uploader.email} after file deletion")
        except Exception as e:
            logger.error(f"Failed to update storage after file deletion: {e}")


# Signals for files app (only register if files app exists)
try:
    from apps.files.models import File
    
    @receiver(post_save, sender=File)
    def update_storage_on_file_save(sender, instance, created, **kwargs):
        """
        Signal handler: Update storage when a file is saved in files app.
        
        This signal automatically updates the user's storage usage
        when a new file is created via the files app.
        
        Args:
            sender: The model class (File)
            instance: The file instance that was saved
            created: Boolean indicating if this is a new file
            **kwargs: Additional signal arguments
        """
        if created and hasattr(instance, 'uploader') and hasattr(instance, 'file_size'):
            # Import here to avoid circular imports
            from .services import StorageService
            
            try:
                # Update storage for the user
                StorageService.update_user_storage(instance.uploader, recalculate=True)
                logger.debug(f"Updated storage for user {instance.uploader.email} after file save")
            except Exception as e:
                logger.error(f"Failed to update storage after file save: {e}")
    
    
    @receiver(post_delete, sender=File)
    def update_storage_on_file_delete(sender, instance, **kwargs):
        """
        Signal handler: Update storage when a file is deleted from files app.
        
        This signal automatically updates the user's storage usage
        when a file is deleted from the files app.
        
        Args:
            sender: The model class (File)
            instance: The file instance that was deleted
            **kwargs: Additional signal arguments
        """
        if hasattr(instance, 'uploader'):
            # Import here to avoid circular imports
            from .services import StorageService
            
            try:
                # Update storage for the user
                StorageService.update_user_storage(instance.uploader, recalculate=True)
                logger.debug(f"Updated storage for user {instance.uploader.email} after file deletion")
            except Exception as e:
                logger.error(f"Failed to update storage after file deletion: {e}")
except ImportError:
    # Files app doesn't exist, skip these signals
    logger.debug("Files app not found, skipping files app storage signals")
    pass

