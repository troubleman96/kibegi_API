from django.urls import path
from .views import (
    NotificationListAPIView,
    MarkNotificationReadAPIView,
    MarkAllReadAPIView,
    DeleteNotificationAPIView,
    UnreadCountAPIView,
)

app_name = 'notifications'

urlpatterns = [
    # List notifications
    path('', NotificationListAPIView.as_view(), name='list'),

    # Fast unread count for UI polling
    path('unread-count/', UnreadCountAPIView.as_view(), name='unread-count'),
    
    # Mark single notification as read
    path('<int:pk>/read/', MarkNotificationReadAPIView.as_view(), name='read'),
    
    # Mark all notifications as read
    path('read-all/', MarkAllReadAPIView.as_view(), name='read-all'),
    
    # Delete notification
    path('<int:pk>/', DeleteNotificationAPIView.as_view(), name='delete'),
]
