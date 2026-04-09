"""Business logic for notifications app"""

from django.db.models import QuerySet
from django.core.exceptions import ValidationError
from typing import Optional


class NotificationService:
    """
    Service layer for notification-related business logic.
    
    This service handles:
    - Creating notifications for different events
    - Retrieving user notifications
    - Marking notifications as read
    - Counting unread notifications
    
    All methods are static as they don't require instance state.
    """
    
    @staticmethod
    def create_notification(
        user,
        notification_type: str,
        content: str,
        related_id: str = ''
    ):
        """
        Create a notification for a user.
        
        Args:
            user: User object who will receive the notification
            notification_type: Type of notification (share_request, friend_request, file_shared)
            content: Human-readable message describing the notification
            related_id: Optional ID of related object (share ID, friendship ID, etc.)
        
        Returns:
            Notification: Created notification object
        
        Example:
            notification = NotificationService.create_notification(
                user=recipient_user,
                notification_type='share_request',
                content='John Doe shared "Assignment.pdf" with you',
                related_id='123'
            )
        """
        from .models import Notification

        valid_types = {t for (t, _) in Notification.TYPE_CHOICES}
        if notification_type not in valid_types:
            raise ValidationError(f"Invalid notification_type: {notification_type}")
        
        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            content=content,
            related_object_id=str(related_id)
        )
        try:
            from apps.core.utils.api_cache import invalidate_cache_namespaces
            invalidate_cache_namespaces('notifications')
        except Exception:
            # Never fail the originating business flow due to cache issues.
            pass

        return notification

    @staticmethod
    def create_bulk(notifications: list[dict]) -> int:
        """
        Create many notifications efficiently.

        Args:
            notifications: list of dicts with keys:
                - user
                - notification_type
                - content
                - related_id (optional)

        Returns:
            int: number created
        """
        from .models import Notification

        valid_types = {t for (t, _) in Notification.TYPE_CHOICES}
        objects = []
        for item in notifications:
            notification_type = item["notification_type"]
            if notification_type not in valid_types:
                raise ValidationError(f"Invalid notification_type: {notification_type}")
            objects.append(
                Notification(
                    user=item["user"],
                    notification_type=notification_type,
                    content=item["content"],
                    related_object_id=str(item.get("related_id", "")),
                )
            )

        if not objects:
            return 0

        Notification.objects.bulk_create(objects)
        try:
            from apps.core.utils.api_cache import invalidate_cache_namespaces
            invalidate_cache_namespaces('notifications')
        except Exception:
            pass
        return len(objects)
    
    @staticmethod
    def get_user_notifications(
        user,
        is_read: Optional[bool] = None,
        notification_type: Optional[str] = None
    ) -> QuerySet:
        """
        Get notifications for a user with optional filters.
        
        Args:
            user: User object whose notifications to retrieve
            is_read: Optional filter by read status (True/False/None for all)
            notification_type: Optional filter by type (share_request, friend_request, file_shared)
        
        Returns:
            QuerySet of Notification objects, ordered by most recent first
        
        Example:
            # Get all unread notifications
            unread = NotificationService.get_user_notifications(user, is_read=False)
            
            # Get all friend request notifications
            friend_reqs = NotificationService.get_user_notifications(
                user,
                notification_type='friend_request'
            )
        """
        from .models import Notification
        
        queryset = Notification.objects.filter(user=user)
        
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read)
        
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        
        return queryset
    
    @staticmethod
    def mark_as_read(notification_id: int, user) -> tuple[bool, str]:
        """
        Mark a notification as read.
        
        Args:
            notification_id: ID of notification to mark as read
            user: User object making the request (for permission check)
        
        Returns:
            Tuple of (success: bool, message: str)
        
        Example:
            success, message = NotificationService.mark_as_read(123, current_user)
            if success:
                print("Notification marked as read")
        """
        from .models import Notification
        
        try:
            notification = Notification.objects.get(id=notification_id, user=user)
        except Notification.DoesNotExist:
            return False, "Notification not found"
        
        if notification.is_read:
            return False, "Notification already marked as read"
        
        notification.mark_as_read()
        return True, "Notification marked as read"
    
    @staticmethod
    def mark_all_as_read(user) -> int:
        """
        Mark all unread notifications for a user as read.
        
        Args:
            user: User object whose notifications to mark as read
        
        Returns:
            int: Number of notifications marked as read
        
        Example:
            count = NotificationService.mark_all_as_read(current_user)
            print(f"Marked {count} notifications as read")
        """
        from .models import Notification
        
        updated = Notification.objects.filter(
            user=user,
            is_read=False
        ).update(is_read=True)
        
        return updated
    
    @staticmethod
    def get_unread_count(user) -> int:
        """
        Get count of unread notifications for a user.
        
        Args:
            user: User object whose unread count to retrieve
        
        Returns:
            int: Number of unread notifications
        
        Example:
            count = NotificationService.get_unread_count(current_user)
            print(f"You have {count} unread notifications")
        """
        from .models import Notification
        
        return Notification.objects.filter(
            user=user,
            is_read=False
        ).count()
    
    @staticmethod
    def delete_notification(notification_id: int, user) -> tuple[bool, str]:
        """
        Delete a notification.
        
        Args:
            notification_id: ID of notification to delete
            user: User object making the request (for permission check)
        
        Returns:
            Tuple of (success: bool, message: str)
        
        Example:
            success, message = NotificationService.delete_notification(123, current_user)
        """
        from .models import Notification
        
        try:
            notification = Notification.objects.get(id=notification_id, user=user)
        except Notification.DoesNotExist:
            return False, "Notification not found"
        
        notification.delete()
        return True, "Notification deleted successfully"
