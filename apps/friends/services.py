from django.contrib.auth import get_user_model
from django.db.models import Q
from .models import Friendship

User = get_user_model()


class FriendService:
    """
    Business logic for friend management.
    
    Handles:
    - User search by email or code
    - Friend request validation
    - Friendship queries
    - Permission checks
    """
    
    @staticmethod
    def search_users(query, current_user, limit=20):
        """
        Search users by email or full name.
        
        Args:
            query: Search string
            current_user: User performing the search (excluded from results)
            limit: Maximum results to return
            
        Returns:
            QuerySet of matching users
        """
        if not query or len(query) < 2:
            return User.objects.none()
        
        # Search by email or full name
        qs = User.objects.filter(
            Q(email__icontains=query) | Q(full_name__icontains=query)
        ).exclude(
            id=current_user.id
        ).filter(
            is_active=True
        )
        
        return qs[:limit]
    
    @staticmethod
    def get_user_by_identifier(identifier):
        """
        Find user by email.
        
        Args:
            identifier: Email address
            
        Returns:
            User object or None
        """
        try:
            return User.objects.get(email=identifier, is_active=True)
        except User.DoesNotExist:
            return None
    
    @staticmethod
    def are_friends(user1, user2):
        """
        Check if two users are friends (accepted friendship).
        
        Args:
            user1: First user
            user2: Second user
            
        Returns:
            Boolean indicating friendship status
        """
        return Friendship.objects.filter(
            Q(user=user1, friend=user2) | Q(user=user2, friend=user1),
            status='accepted'
        ).exists()
    
    @staticmethod
    def friendship_exists(user1, user2):
        """
        Check if any friendship (pending or accepted) exists.
        
        Args:
            user1: First user
            user2: Second user
            
        Returns:
            Boolean indicating if friendship exists
        """
        return Friendship.objects.filter(
            Q(user=user1, friend=user2) | Q(user=user2, friend=user1)
        ).exists()
    
    @staticmethod
    def get_friendship(user1, user2):
        """
        Get friendship between two users (either direction).
        
        Args:
            user1: First user
            user2: Second user
            
        Returns:
            Friendship object or None
        """
        return Friendship.objects.filter(
            Q(user=user1, friend=user2) | Q(user=user2, friend=user1)
        ).first()
    
    @staticmethod
    def get_friends_list(user, status=None):
        """
        Get list of user's friends.
        
        Args:
            user: User to get friends for
            status: Filter by status (pending/accepted), None for all
            
        Returns:
            QuerySet of Friendship objects
        """
        qs = Friendship.objects.filter(
            Q(user=user) | Q(friend=user)
        ).select_related('user', 'friend')
        
        if status:
            qs = qs.filter(status=status)
        
        return qs
    
    @staticmethod
    def get_friend_requests(user):
        """
        Get pending friend requests received by user.
        
        Args:
            user: User to get requests for
            
        Returns:
            QuerySet of pending Friendship objects where user is the friend
        """
        return Friendship.objects.filter(
            friend=user,
            status='pending'
        ).select_related('user')
    
    @staticmethod
    def get_sent_requests(user):
        """
        Get pending friend requests sent by user.
        
        Args:
            user: User who sent requests
            
        Returns:
            QuerySet of pending Friendship objects where user is the sender
        """
        return Friendship.objects.filter(
            user=user,
            status='pending'
        ).select_related('friend')
    
    @staticmethod
    def can_send_request(sender, recipient):
        """
        Check if user can send friend request.
        
        Args:
            sender: User sending request
            recipient: User receiving request
            
        Returns:
            Tuple of (can_send: bool, error_message: str)
        """
        # Cannot send to self
        if sender.id == recipient.id:
            return False, "Cannot send friend request to yourself"
        
        # Check if friendship already exists
        if FriendService.friendship_exists(sender, recipient):
            return False, "Friendship already exists or request pending"
        
        return True, ""
    
    @staticmethod
    def create_friend_request(sender, recipient):
        """
        Create a new friend request.
        
        Args:
            sender: User sending request
            recipient: User receiving request
            
        Returns:
            Friendship object
            
        Raises:
            ValueError: If request cannot be created
        """
        can_send, error = FriendService.can_send_request(sender, recipient)
        if not can_send:
            raise ValueError(error)
        
        friendship = Friendship.objects.create(
            user=sender,
            friend=recipient,
            status='pending'
        )

        try:
            from apps.notifications.services import NotificationService

            sender_name = getattr(sender, "full_name", "Someone")
            content = f"{sender_name} sent you a friend request"
            NotificationService.create_notification(
                user=recipient,
                notification_type="friend_request",
                content=content,
                related_id=str(friendship.id),
            )
        except Exception:
            pass
        
        return friendship
