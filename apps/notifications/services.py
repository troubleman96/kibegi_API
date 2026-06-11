"""Business logic for notifications app"""

import logging
from django.db.models import QuerySet
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from typing import Optional

logger = logging.getLogger('kibegi')


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


class ClassUpdateNotifier:
    """Notifies class members when a lecturer uploads new material."""

    PRIMARY_COLOR = "#4F46E5"
    TEXT_COLOR = "#1F2937"
    TEXT_LIGHT = "#6B7280"
    BACKGROUND = "#F9FAFB"

    @classmethod
    def notify_new_upload(cls, upload) -> None:
        """Dispatch in-app, email and SMS notifications for a new class upload."""
        try:
            cls._dispatch(upload)
        except Exception as exc:
            logger.error("ClassUpdateNotifier.notify_new_upload failed: %s", exc, exc_info=True)

    @classmethod
    def _dispatch(cls, upload) -> None:
        from apps.classes.models import Membership

        class_obj = upload.class_obj
        uploader = upload.uploader

        members = list(
            Membership.objects.filter(class_obj=class_obj)
            .exclude(user=uploader)
            .select_related('user')
        )
        if not members:
            return

        content = (
            f"{uploader.full_name} uploaded '{upload.file_name}' "
            f"in {class_obj.name}."
        )

        # In-app notifications (bulk)
        NotificationService.create_bulk([
            {
                'user': m.user,
                'notification_type': 'class_update',
                'content': content,
                'related_id': str(upload.id),
            }
            for m in members
        ])

        # Email + SMS (per member)
        for membership in members:
            member = membership.user
            cls._send_email(member, upload, class_obj, uploader)
            cls._send_sms(member, upload, class_obj, uploader)

    @classmethod
    def _send_email(cls, member, upload, class_obj, uploader) -> None:
        subject = f"📚 New material in {class_obj.name}"
        preview = f"{uploader.full_name} uploaded {upload.file_name}"
        html_body = f"""
<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:{cls.BACKGROUND};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table width="100%" cellspacing="0" cellpadding="0">
    <tr><td align="center" style="padding:40px 20px;">
      <table width="600" cellspacing="0" cellpadding="0" style="background:#fff;border-radius:16px;box-shadow:0 4px 6px rgba(0,0,0,.05);">
        <tr><td style="padding:30px 40px;border-bottom:1px solid #E5E7EB;text-align:center;">
          <div style="display:inline-block;background:linear-gradient(135deg,{cls.PRIMARY_COLOR},{cls.PRIMARY_COLOR}cc);padding:10px 22px;border-radius:10px;">
            <span style="font-size:24px;font-weight:700;color:#fff;">📚 Kibegi</span>
          </div>
        </td></tr>
        <tr><td style="padding:35px 40px;">
          <h2 style="margin:0 0 16px;font-size:20px;color:{cls.TEXT_COLOR};">New material posted</h2>
          <p style="margin:0 0 12px;font-size:15px;color:{cls.TEXT_LIGHT};">
            Hello <strong>{member.full_name}</strong>,
          </p>
          <p style="margin:0 0 20px;font-size:15px;color:{cls.TEXT_LIGHT};line-height:1.6;">
            <strong>{uploader.full_name}</strong> just uploaded a new file to
            <strong>{class_obj.name}</strong>:
          </p>
          <div style="background:#EEF2FF;border-left:4px solid {cls.PRIMARY_COLOR};border-radius:8px;padding:16px 20px;margin-bottom:20px;">
            <p style="margin:0;font-size:15px;font-weight:600;color:{cls.TEXT_COLOR};">{upload.file_name}</p>
            <p style="margin:4px 0 0;font-size:13px;color:{cls.TEXT_LIGHT};">
              Type: {upload.file_type.capitalize()} &nbsp;|&nbsp;
              Size: {round(upload.file_size / 1024, 1)} KB
            </p>
          </div>
          <p style="margin:0;font-size:14px;color:{cls.TEXT_LIGHT};">Log in to Kibegi to view and download the file.</p>
        </td></tr>
        <tr><td style="padding:20px 40px 30px;background:{cls.BACKGROUND};border-radius:0 0 16px 16px;text-align:center;">
          <p style="margin:0;font-size:12px;color:{cls.TEXT_LIGHT};">© 2025 Kibegi. All rights reserved.</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>
"""
        plain = (
            f"Hello {member.full_name},\n\n"
            f"{uploader.full_name} uploaded '{upload.file_name}' in {class_obj.name}.\n\n"
            f"Log in to Kibegi to view and download the file.\n\n© 2025 Kibegi."
        )
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
        if not from_email:
            return
        try:
            msg = EmailMultiAlternatives(subject, plain, from_email, [member.email])
            msg.attach_alternative(html_body, "text/html")
            msg.send(fail_silently=True)
        except Exception as exc:
            logger.warning("Email to %s failed: %s", member.email, exc)

    @classmethod
    def _send_sms(cls, member, upload, class_obj, uploader) -> None:
        """Send SMS via the member's own SMS account if they have one with credits."""
        try:
            from apps.sms.services import SmsService
            account = SmsService.get_account_for_owner(member)
            if not account.is_active or account.balance_credits < 1:
                return
            if not account.phone_number:
                return
            message = (
                f"[Kibegi] {uploader.full_name} uploaded '{upload.file_name}' "
                f"in {class_obj.name}. Log in to view."
            )
            SmsService.send_single(account, account.phone_number, message, context=upload)
        except Exception as exc:
            logger.warning("SMS to member %s failed: %s", member.id, exc)
