from rest_framework import serializers
from .models import Friendship
from apps.authentication.models import User
from apps.authentication.serializers import UserSummarySerializer


class UserSearchSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for user search results.
    
    Shows basic user info for friend search.
    """
    profile_image_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'user_type', 'profile_image', 'profile_image_url']
        read_only_fields = fields

    def get_profile_image_url(self, obj):
        return UserSummarySerializer(context=self.context).get_profile_image_url(obj)


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
    user_profile_image = serializers.ImageField(source='user.profile_image', read_only=True)
    user_profile_image_url = serializers.SerializerMethodField()
    friend_profile_image = serializers.ImageField(source='friend.profile_image', read_only=True)
    friend_profile_image_url = serializers.SerializerMethodField()
    display_name = serializers.CharField(read_only=True)
    
    class Meta:
        model = Friendship
        fields = [
            'id', 'user', 'user_email', 'user_name',
            'user_profile_image', 'user_profile_image_url',
            'friend', 'friend_email', 'friend_name', 'friend_profile_image', 'friend_profile_image_url',
            'nickname', 'display_name', 'status',
            'created_at', 'accepted_at'
        ]
        read_only_fields = [
            'id', 'user', 'friend', 'status',
            'created_at', 'accepted_at'
        ]

    def get_user_profile_image_url(self, obj):
        return UserSummarySerializer(context=self.context).get_profile_image_url(obj.user)

    def get_friend_profile_image_url(self, obj):
        return UserSummarySerializer(context=self.context).get_profile_image_url(obj.friend)


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
        
        return UserSummarySerializer(friend, context=self.context).data


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


class DeclineFriendSerializer(serializers.Serializer):
    """
    Empty serializer for decline action.
    
    No input needed - friend request ID comes from URL.
    Used for Swagger schema generation.
    """
    pass


class FriendRequestSerializer(serializers.ModelSerializer):
    """
    Serializer for friend request details.
    
    Shows who sent the request and when, with additional context
    for the UI to display properly.
    """
    sender_id = serializers.UUIDField(source='user.id', read_only=True)
    sender_email = serializers.CharField(source='user.email', read_only=True)
    sender_name = serializers.CharField(source='user.full_name', read_only=True)
    sender_type = serializers.CharField(source='user.user_type', read_only=True)
    sender_profile_image = serializers.ImageField(source='user.profile_image', read_only=True)
    sender_profile_image_url = serializers.SerializerMethodField()
    recipient_id = serializers.UUIDField(source='friend.id', read_only=True)
    recipient_email = serializers.CharField(source='friend.email', read_only=True)
    recipient_name = serializers.CharField(source='friend.full_name', read_only=True)
    recipient_type = serializers.CharField(source='friend.user_type', read_only=True)
    recipient_profile_image = serializers.ImageField(source='friend.profile_image', read_only=True)
    recipient_profile_image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Friendship
        fields = [
            'id', 
            'sender_id', 'sender_email', 'sender_name', 'sender_type', 'sender_profile_image', 'sender_profile_image_url',
            'recipient_id', 'recipient_email', 'recipient_name', 'recipient_type', 'recipient_profile_image', 'recipient_profile_image_url',
            'status', 'created_at'
        ]
        read_only_fields = fields

    def get_sender_profile_image_url(self, obj):
        return UserSummarySerializer(context=self.context).get_profile_image_url(obj.user)

    def get_recipient_profile_image_url(self, obj):
        return UserSummarySerializer(context=self.context).get_profile_image_url(obj.friend)
