from django.urls import path
from .views import (
    ClassListCreateAPIView,
    ClassDetailAPIView,
    ClassSearchAPIView,
    JoinClassAPIView,
    ClassMembersAPIView,
    LeaveClassAPIView,
)

app_name = 'classes'

urlpatterns = [
    path('', ClassListCreateAPIView.as_view(), name='list-create'),
    path('search/', ClassSearchAPIView.as_view(), name='search'),
    path('join/', JoinClassAPIView.as_view(), name='join'),
    path('<uuid:pk>/', ClassDetailAPIView.as_view(), name='detail'),
    path('<uuid:pk>/members/', ClassMembersAPIView.as_view(), name='members'),
    path('<uuid:pk>/leave/', LeaveClassAPIView.as_view(), name='leave'),
]
