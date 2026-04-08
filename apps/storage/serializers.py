"""
Storage App Serializers

This module defines serializers for the storage API endpoints.
Serializers convert model instances to/from JSON for API responses.
"""
from rest_framework import serializers
from .models import UserStorage, StorageUsageHistory


class UserStorageSerializer(serializers.ModelSerializer):
    """
    Serializer for UserStorage model.
    
    This serializer includes:
    - All model fields
    - Computed properties (used_storage_mb, free_storage_mb, etc.)
    - User information
    """
    
    # Computed properties (read-only)
    used_storage_mb = serializers.ReadOnlyField(help_text="Storage used in megabytes")
    free_storage_mb = serializers.ReadOnlyField(help_text="Free storage available in megabytes")
    free_storage_bytes = serializers.ReadOnlyField(help_text="Free storage available in bytes")
    usage_percentage = serializers.ReadOnlyField(help_text="Storage usage as percentage (0-100)")
    is_full = serializers.ReadOnlyField(help_text="Whether storage is full")
    is_near_limit = serializers.SerializerMethodField(help_text="Whether storage is near limit (90%)")
    
    # User information
    user_email = serializers.EmailField(source='user.email', read_only=True, help_text="User's email address")
    user_full_name = serializers.CharField(source='user.full_name', read_only=True, help_text="User's full name")
    
    class Meta:
        model = UserStorage
        fields = [
            'id',
            'user',
            'user_email',
            'user_full_name',
            'total_quota_mb',
            'used_storage_bytes',
            'used_storage_mb',
            'free_storage_mb',
            'free_storage_bytes',
            'usage_percentage',
            'is_full',
            'is_near_limit',
            'created_at',
            'updated_at',
            'last_calculated',
        ]
        read_only_fields = [
            'id',
            'user',
            'used_storage_bytes',
            'created_at',
            'updated_at',
            'last_calculated',
        ]
    
    def get_is_near_limit(self, obj):
        """Check if storage is near limit (90% or more)"""
        return obj.is_near_limit()


class StorageInfoSerializer(serializers.Serializer):
    """
    Serializer for storage information summary.
    
    This serializer is used for the storage info endpoint
    and provides a clean, user-friendly format.
    """
    
    total_quota_mb = serializers.FloatField(help_text="Total storage quota in megabytes")
    used_storage_mb = serializers.FloatField(help_text="Storage used in megabytes")
    free_storage_mb = serializers.FloatField(help_text="Free storage available in megabytes")
    used_storage_bytes = serializers.IntegerField(help_text="Storage used in bytes")
    free_storage_bytes = serializers.IntegerField(help_text="Free storage available in bytes")
    usage_percentage = serializers.FloatField(help_text="Storage usage as percentage (0-100)")
    is_full = serializers.BooleanField(help_text="Whether storage is full")
    is_near_limit = serializers.BooleanField(help_text="Whether storage is near limit (90%)")
    last_calculated = serializers.DateTimeField(allow_null=True, help_text="When storage was last calculated")


class StorageUsageHistorySerializer(serializers.ModelSerializer):
    """
    Serializer for StorageUsageHistory model.
    
    Used for viewing historical storage usage data.
    """
    
    used_storage_mb = serializers.SerializerMethodField(help_text="Storage used in megabytes")
    
    class Meta:
        model = StorageUsageHistory
        fields = [
            'id',
            'user_storage',
            'used_storage_bytes',
            'used_storage_mb',
            'recorded_at',
        ]
        read_only_fields = ['id', 'recorded_at']
    
    def get_used_storage_mb(self, obj):
        """Convert bytes to megabytes"""
        return round(obj.used_storage_bytes / (1024 * 1024), 2)


