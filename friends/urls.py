from django.urls import path
from .views import (
    FriendshipListAPIView,
    AddFriendAPIView,
    SearchUsersAPIView,
    AcceptFriendRequestAPIView,
    UpdateNicknameAPIView,
    RemoveFriendAPIView,
)

app_name = 'friends'

urlpatterns = [
    # List friends
    path('', FriendshipListAPIView.as_view(), name='list'),
    
    # Send friend request
    path('add/', AddFriendAPIView.as_view(), name='add'),
    
    # Search users
    path('search/', SearchUsersAPIView.as_view(), name='search'),
    
    # Accept friend request
    path('<int:pk>/accept/', AcceptFriendRequestAPIView.as_view(), name='accept'),
    
    # Update nickname
    path('<int:pk>/nickname/', UpdateNicknameAPIView.as_view(), name='nickname'),
    
    # Remove friend
    path('<int:pk>/', RemoveFriendAPIView.as_view(), name='remove'),
]
