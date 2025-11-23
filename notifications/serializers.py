from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """
    Serializer for Notification model.
    
    Provides full notification details including:
    - ID and type
    - Content message
    - Related object ID
    - Read status
    - Timestamp
    
    Used for:
    - Listing notifications
    - Showing notification details
    - Returning created notifications
    """
    
    class Meta:
        model = Notification
        fields = [
            'id',
            'notification_type',
            'content',
            'related_object_id',
            'is_read',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class NotificationListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for notification lists.
    
    Same as NotificationSerializer but could be optimized
    in the future to exclude certain fields for performance.
    """
    
    class Meta:
        model = Notification
        fields = [
            'id',
            'notification_type',
            'content',
            'related_object_id',
            'is_read',
            'created_at',
        ]
        read_only_fields = fields


class MarkAsReadSerializer(serializers.Serializer):
    """
    Serializer for marking notification as read.
    
    No input fields required - just the notification ID from URL.
    Used to validate the mark-as-read action.
    """
    pass  # No fields needed, just validates the action
