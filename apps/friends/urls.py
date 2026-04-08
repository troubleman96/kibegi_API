from django.urls import path
from .views import (
    FriendshipListAPIView,
    AddFriendAPIView,
    SearchUsersAPIView,
    AcceptFriendRequestAPIView,
    UpdateNicknameAPIView,
    RemoveFriendAPIView,
    IncomingFriendRequestsAPIView,
    SentFriendRequestsAPIView,
    DeclineFriendRequestAPIView,
    CancelFriendRequestAPIView,
)

app_name = 'friends'

urlpatterns = [
    # =========================================================================
    # Friend List & Search
    # =========================================================================
    
    # List all friends (with optional status filter)
    path('', FriendshipListAPIView.as_view(), name='list'),
    
    # Search users to add as friends
    path('search/', SearchUsersAPIView.as_view(), name='search'),
    
    # =========================================================================
    # Friend Requests Management
    # =========================================================================
    
    # List incoming friend requests (received by current user)
    path('requests/incoming/', IncomingFriendRequestsAPIView.as_view(), name='requests-incoming'),
    
    # List sent friend requests (sent by current user)
    path('requests/sent/', SentFriendRequestsAPIView.as_view(), name='requests-sent'),
    
    # Send a new friend request
    path('add/', AddFriendAPIView.as_view(), name='add'),
    
    # Accept a friend request
    path('<int:pk>/accept/', AcceptFriendRequestAPIView.as_view(), name='accept'),
    
    # Decline a friend request (for recipient)
    path('<int:pk>/decline/', DeclineFriendRequestAPIView.as_view(), name='decline'),
    
    # Cancel a sent friend request (for sender)
    path('<int:pk>/cancel/', CancelFriendRequestAPIView.as_view(), name='cancel'),
    
    # =========================================================================
    # Friend Management
    # =========================================================================
    
    # Update friend nickname
    path('<int:pk>/nickname/', UpdateNicknameAPIView.as_view(), name='nickname'),
    
    # Remove friend / unfriend
    path('<int:pk>/', RemoveFriendAPIView.as_view(), name='remove'),
]
