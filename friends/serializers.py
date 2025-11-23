from rest_framework import serializers
from .models import Friendship
from authentication.models import User


class UserSearchSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for user search results.
    
    Shows basic user info for friend search.
    """
    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'user_type']
        read_only_fields = fields


class AddFriendSerializer(serializers.Serializer):
    """
    Serializer for sending friend requests.
    
    Accepts either user_id or email to identify the friend.
    """
    user_id = serializers.IntegerField(
        required=False,
        help_text="ID of user to add as friend"
    )
    email = serializers.EmailField(
        required=False,
        help_text="Email of user to add as friend"
    )
    
    def validate(self, data):
        """Validate that either user_id or email is provided"""
        if not data.get('user_id') and not data.get('email'):
            raise serializers.ValidationError(
                "Either user_id or email must be provided"
            )
        return data


class FriendshipSerializer(serializers.ModelSerializer):
    """
    Full serializer for Friendship with nested user data.
    
    Shows complete friendship details including both users.
    """
    user_email = serializers.CharField(
        source='user.email',
        read_only=True
    )
    user_name = serializers.CharField(
        source='user.full_name',
        read_only=True
    )
    friend_email = serializers.CharField(
        source='friend.email',
        read_only=True
    )
    friend_name = serializers.CharField(
        source='friend.full_name',
        read_only=True
    )
    display_name = serializers.CharField(read_only=True)
    
    class Meta:
        model = Friendship
        fields = [
            'id', 'user', 'user_email', 'user_name',
            'friend', 'friend_email', 'friend_name',
            'nickname', 'display_name', 'status',
            'created_at', 'accepted_at'
        ]
        read_only_fields = [
            'id', 'user', 'friend', 'status',
            'created_at', 'accepted_at'
        ]


class FriendshipListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing friendships.
    
    Shows essential info only for better performance in lists.
    Used in friend list endpoints.
    """
    friend_info = serializers.SerializerMethodField()
    
    class Meta:
        model = Friendship
        fields = [
            'id', 'friend_info', 'nickname',
            'display_name', 'status', 'created_at'
        ]
    
    def get_friend_info(self, obj):
        """
        Get info about the friend (not the current user).
        
        Returns the other user in the friendship relationship.
        """
        request = self.context.get('request')
        if not request:
            return None
        
        current_user = request.user
        
        # Determine which user is the friend
        if obj.user == current_user:
            friend = obj.friend
        else:
            friend = obj.user
        
        return {
            'id': friend.id,
            'email': friend.email,
            'full_name': friend.full_name,
            'user_type': friend.user_type
        }


class UpdateNicknameSerializer(serializers.Serializer):
    """
    Serializer for updating friend nickname.
    
    Allows users to set custom names for their friends.
    """
    nickname = serializers.CharField(
        max_length=100,
        allow_blank=True,
        help_text="Custom nickname for the friend (leave blank to remove)"
    )


class AcceptFriendSerializer(serializers.Serializer):
    """
    Empty serializer for accept action.
    
    No input needed - friend request ID comes from URL.
    Used for Swagger schema generation.
    """
    pass
