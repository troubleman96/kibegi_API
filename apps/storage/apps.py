"""
Storage App Configuration

This module configures the storage app and registers signals.
"""
from django.apps import AppConfig


class StorageConfig(AppConfig):
    """
    App configuration for the storage app.
    
    This class registers signals when the app is ready.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.storage'
    
    def ready(self):
        """
        Called when Django starts.
        
        This method imports and registers signals for the storage app.
        """
        import apps.storage.signals  # noqa
