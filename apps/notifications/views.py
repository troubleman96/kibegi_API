from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from .models import Notification
from .serializers import NotificationSerializer, NotificationListSerializer, MarkAsReadSerializer
from .services import NotificationService
from apps.core.utils.responses import success_response, error_response
from apps.core.utils.api_cache import build_cache_key, get_cached_response, cache_response, invalidate_cache_namespaces


class NotificationPagination(PageNumberPagination):
    """Pagination for notification list"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class NotificationListAPIView(APIView):
    """
    List notifications for the authenticated user.
    
    GET /api/v1/notifications/
    
    Query Parameters:
        - is_read: Filter by read status (true/false/all)
        - type: Filter by notification type (share_request, friend_request, file_shared)
    
    Returns paginated list of notifications, ordered by most recent first.
    Also includes unread count in response.
    """
    
    permission_classes = [IsAuthenticated]
    pagination_class = NotificationPagination
    
    @extend_schema(
        summary="List Notifications",
        description="Get list of notifications for authenticated user with optional filters",
        parameters=[
            OpenApiParameter(
                name='is_read',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by read status: true, false, or all (default: all)',
                required=False,
            ),
            OpenApiParameter(
                name='type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by type: share_request, friend_request, file_shared',
                required=False,
            ),
        ],
        responses={
            200: NotificationListSerializer(many=True),
        },
        tags=['Notifications'],
    )
    def get(self, request):
        """Get list of notifications"""
        cache_key = build_cache_key(request, 'notifications')
        cached_response = get_cached_response(cache_key)
        if cached_response is not None:
            return cached_response
        # Get query parameters
        is_read_param = request.query_params.get('is_read', 'all').lower()
        notification_type = request.query_params.get('type', None)
        
        # Convert is_read parameter to boolean or None
        if is_read_param == 'true':
            is_read = True
        elif is_read_param == 'false':
            is_read = False
        else:
            is_read = None  # Get all notifications
        
        # Get notifications using service
        notifications = NotificationService.get_user_notifications(
            user=request.user,
            is_read=is_read,
            notification_type=notification_type
        )
        
        # Get unread count
        unread_count = NotificationService.get_unread_count(request.user)
        
        # Paginate results
        paginator = self.pagination_class()
        paginated_notifications = paginator.paginate_queryset(notifications, request)
        
        # Serialize
        serializer = NotificationListSerializer(paginated_notifications, many=True)
        
        # Return paginated response with unread count
        paginated_response = paginator.get_paginated_response(serializer.data)
        paginated_response.data['unread_count'] = unread_count
        
        response = success_response(
            data=paginated_response.data,
            message=f"Retrieved {notifications.count()} notifications"
        )
        return cache_response(cache_key, response, 'notifications')


class MarkNotificationReadAPIView(APIView):
    """
    Mark a specific notification as read.
    
    POST /api/v1/notifications/{id}/read/
    
    Marks the specified notification as read.
    Only the notification owner can mark it as read.
    """
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Mark Notification as Read",
        description="Mark a specific notification as read",
        request=MarkAsReadSerializer,
        responses={
            200: NotificationSerializer,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
        tags=['Notifications'],
    )
    def post(self, request, pk):
        """Mark notification as read"""
        success, message = NotificationService.mark_as_read(
            notification_id=pk,
            user=request.user
        )
        
        if not success:
            if "not found" in message:
                return error_response(
                    message=message,
                    status_code=404
                )
            return error_response(
                message=message,
                status_code=400
            )
        
        # Get updated notification
        notification = Notification.objects.get(id=pk)
        serializer = NotificationSerializer(notification)
        invalidate_cache_namespaces('notifications')
        
        return success_response(
            data=serializer.data,
            message=message
        )


class MarkAllReadAPIView(APIView):
    """
    Mark all notifications as read.
    
    POST /api/v1/notifications/read-all/
    
    Marks all unread notifications for the authenticated user as read.
    Returns count of notifications that were marked as read.
    """
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Mark All Notifications as Read",
        description="Mark all unread notifications for the user as read",
        request=None,
        responses={
            200: OpenApiTypes.OBJECT,
        },
        tags=['Notifications'],
    )
    def post(self, request):
        """Mark all notifications as read"""
        count = NotificationService.mark_all_as_read(request.user)
        invalidate_cache_namespaces('notifications')
        
        return success_response(
            data={'marked_read': count},
            message=f"Marked {count} notifications as read"
        )


class DeleteNotificationAPIView(APIView):
    """
    Delete a notification.
    
    DELETE /api/v1/notifications/{id}/
    
    Deletes the specified notification.
    Only the notification owner can delete it.
    """
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Delete Notification",
        description="Delete a specific notification",
        responses={
            200: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
        tags=['Notifications'],
    )
    def delete(self, request, pk):
        """Delete notification"""
        success, message = NotificationService.delete_notification(
            notification_id=pk,
            user=request.user
        )
        
        if not success:
            return error_response(
                message=message,
                status_code=404
            )
        invalidate_cache_namespaces('notifications')
        
        return success_response(
            message=message
        )
