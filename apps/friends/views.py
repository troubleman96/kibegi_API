import logging
from rest_framework.views import APIView
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter
from .models import Friendship
from .serializers import (
    FriendshipSerializer, FriendshipListSerializer, AddFriendSerializer,
    UserSearchSerializer, UpdateNicknameSerializer, AcceptFriendSerializer,
    DeclineFriendSerializer, FriendRequestSerializer
)
from .services import FriendService
from apps.core.utils.responses import success_response, error_response
from apps.core.pagination import StandardResultsSetPagination

# Logger for friends app
logger = logging.getLogger('kibegi')


@extend_schema(tags=['Friends'])
class FriendshipListAPIView(generics.ListAPIView):
    """
    List all friendships for the current user.
    
    GET: Get friends list with optional status filter.
    Query param 'status' can be: pending, accepted, or all (default).
    """
    permission_classes = [IsAuthenticated]
    serializer_class = FriendshipListSerializer
    pagination_class = StandardResultsSetPagination
    
    @extend_schema(
        summary="List friends",
        description="Get list of friends and friend requests. "
                    "Filter by status: pending, accepted, or all.",
        parameters=[
            OpenApiParameter(
                name='status',
                description='Filter by status',
                required=False,
                type=str,
                enum=['pending', 'accepted', 'all']
            )
        ]
    )
    def get_queryset(self):
        """Get friendships for current user"""
        status_filter = self.request.query_params.get('status', 'accepted')
        logger.debug(f"User {self.request.user.email} fetching friends list with status={status_filter}")
        
        if status_filter == 'all':
            return FriendService.get_friends_list(self.request.user)
        else:
            return FriendService.get_friends_list(
                self.request.user,
                status=status_filter
            )
    
    def list(self, request, *args, **kwargs):
        """Return paginated list of friends"""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        logger.info(f"User {request.user.email} retrieved {queryset.count()} friendships")
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return success_response(
            message="Friends list retrieved successfully",
            data=serializer.data
        )


@extend_schema(tags=['Friends'])
class AddFriendAPIView(APIView):
    """
    Send a friend request.
    
    POST: Send friend request by user_id or email.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = AddFriendSerializer
    
    @extend_schema(
        summary="Send friend request",
        description="Send a friend request to another user by ID or email.",
        request=AddFriendSerializer,
        responses={201: FriendshipSerializer}
    )
    def post(self, request):
        """Send friend request"""
        serializer = AddFriendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Find the recipient
        user_id = serializer.validated_data.get('user_id')
        email = serializer.validated_data.get('email')
        
        logger.debug(f"User {request.user.email} attempting to send friend request to user_id={user_id}, email={email}")
        
        if user_id:
            try:
                recipient = request.user.__class__.objects.get(id=user_id)
            except request.user.__class__.DoesNotExist:
                logger.warning(f"Friend request failed: User ID {user_id} not found")
                return error_response(
                    message="User not found",
                    status_code=status.HTTP_404_NOT_FOUND
                )
        else:
            recipient = FriendService.get_user_by_identifier(email)
            if not recipient:
                logger.warning(f"Friend request failed: Email {email} not found")
                return error_response(
                    message="User not found",
                    status_code=status.HTTP_404_NOT_FOUND
                )
        
        # Create friend request
        try:
            friendship = FriendService.create_friend_request(
                sender=request.user,
                recipient=recipient
            )
            
            logger.info(f"Friend request sent: {request.user.email} -> {recipient.email} (ID: {friendship.id})")
            
            response_serializer = FriendshipSerializer(friendship)
            return success_response(
                message="Friend request sent successfully",
                data=response_serializer.data,
                status_code=status.HTTP_201_CREATED
            )
        except ValueError as e:
            logger.warning(f"Friend request failed from {request.user.email} to {recipient.email}: {str(e)}")
            return error_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST
            )


@extend_schema(tags=['Friends'])
class SearchUsersAPIView(generics.ListAPIView):
    """
    Search for users to add as friends.
    
    GET: Search users by email or name.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserSearchSerializer
    
    @extend_schema(
        summary="Search users",
        description="Search for users by email or full name to add as friends.",
        parameters=[
            OpenApiParameter(
                name='q',
                description='Search query (min 2 characters)',
                required=True,
                type=str
            )
        ]
    )
    def get_queryset(self):
        """Search users based on query"""
        query = self.request.query_params.get('q', '')
        return FriendService.search_users(query, self.request.user)
    
    def list(self, request, *args, **kwargs):
        """Return search results"""
        query = request.query_params.get('q', '')
        
        if not query or len(query) < 2:
            return error_response(
                message="Search query must be at least 2 characters",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        return success_response(
            message=f"Found {len(serializer.data)} users",
            data=serializer.data
        )


@extend_schema(tags=['Friends'])
class AcceptFriendRequestAPIView(APIView):
    """
    Accept a friend request.
    
    POST: Accept a pending friend request.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = AcceptFriendSerializer
    
    @extend_schema(
        summary="Accept friend request",
        description="Accept a pending friend request sent to you.",
        responses={200: FriendshipSerializer}
    )
    def post(self, request, pk):
        """Accept friend request"""
        logger.debug(f"User {request.user.email} attempting to accept friend request ID={pk}")
        
        # Get the friendship
        try:
            friendship = Friendship.objects.get(id=pk)
        except Friendship.DoesNotExist:
            logger.warning(f"Accept friend request failed: Request ID {pk} not found")
            return error_response(
                message="Friend request not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Check if current user is the recipient
        if friendship.friend != request.user:
            logger.warning(f"Accept friend request denied: User {request.user.email} is not the recipient of request {pk}")
            return error_response(
                message="You can only accept requests sent to you",
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        # Check if already accepted
        if friendship.is_accepted():
            logger.info(f"Friend request {pk} already accepted")
            return error_response(
                message="Friend request already accepted",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Accept the request
        friendship.accept()
        
        logger.info(f"Friend request accepted: {friendship.user.email} <-> {friendship.friend.email} (ID: {pk})")
        
        response_serializer = FriendshipSerializer(friendship)
        return success_response(
            message="Friend request accepted",
            data=response_serializer.data
        )


@extend_schema(tags=['Friends'])
class UpdateNicknameAPIView(APIView):
    """
    Update friend nickname.
    
    PATCH: Set or update custom nickname for a friend.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UpdateNicknameSerializer
    
    @extend_schema(
        summary="Update friend nickname",
        description="Set or update a custom nickname for your friend.",
        request=UpdateNicknameSerializer,
        responses={200: FriendshipSerializer}
    )
    def patch(self, request, pk):
        """Update friend nickname"""
        logger.debug(f"User {request.user.email} updating nickname for friendship {pk}")
        
        # Get the friendship
        try:
            friendship = Friendship.objects.get(id=pk)
        except Friendship.DoesNotExist:
            logger.warning(f"Update nickname failed: Friendship {pk} not found")
            return error_response(
                message="Friendship not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Check if user is part of this friendship
        if friendship.user != request.user and friendship.friend != request.user:
            logger.warning(f"Update nickname denied: User {request.user.email} not part of friendship {pk}")
            return error_response(
                message="You can only update nicknames for your own friends",
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        # Check if friendship is accepted
        if not friendship.is_accepted():
            logger.warning(f"Update nickname denied: Friendship {pk} not yet accepted")
            return error_response(
                message="Can only set nicknames for accepted friends",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Update nickname
        serializer = UpdateNicknameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Only the user who set the nickname can change it
        # If current user is 'friend', we need to swap to make them the 'user'
        if friendship.friend == request.user:
            # Find or create the reverse friendship for nickname
            reverse_friendship, created = Friendship.objects.get_or_create(
                user=request.user,
                friend=friendship.user,
                defaults={'status': 'accepted'}
            )
            friendship = reverse_friendship
        
        old_nickname = friendship.nickname
        friendship.nickname = serializer.validated_data['nickname']
        friendship.save()
        
        logger.info(f"Nickname updated for friendship {pk}: '{old_nickname}' -> '{friendship.nickname}'")
        
        response_serializer = FriendshipSerializer(friendship)
        return success_response(
            message="Nickname updated successfully",
            data=response_serializer.data
        )


@extend_schema(tags=['Friends'])
class RemoveFriendAPIView(APIView):
    """
    Remove a friend.
    
    DELETE: Remove/unfriend a user.
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Remove friend",
        description="Remove a friend or cancel a friend request.",
        responses={200: dict}
    )
    def delete(self, request, pk):
        """Remove friend"""
        logger.debug(f"User {request.user.email} attempting to remove friendship {pk}")
        
        # Get the friendship
        try:
            friendship = Friendship.objects.get(id=pk)
        except Friendship.DoesNotExist:
            logger.warning(f"Remove friend failed: Friendship {pk} not found")
            return error_response(
                message="Friendship not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Check if user is part of this friendship
        if friendship.user != request.user and friendship.friend != request.user:
            logger.warning(f"Remove friend denied: User {request.user.email} not part of friendship {pk}")
            return error_response(
                message="You can only remove your own friends",
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        # Store info for logging before deletion
        user_email = friendship.user.email
        friend_email = friendship.friend.email
        friendship_status = friendship.status
        
        # Delete the friendship
        friendship.delete()
        
        # Also delete reverse friendship if it exists
        Friendship.objects.filter(
            user=friendship.friend,
            friend=friendship.user
        ).delete()
        
        logger.info(f"Friendship removed: {user_email} <-> {friend_email} (was {friendship_status})")
        
        return success_response(
            message="Friend removed successfully"
        )


# ============================================================================
# Friend Request Management Endpoints
# ============================================================================

@extend_schema(tags=['Friends'])
class IncomingFriendRequestsAPIView(generics.ListAPIView):
    """
    List all incoming (received) friend requests.
    
    GET: Get all pending friend requests sent TO the current user.
    These are requests waiting for the user to accept or decline.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = FriendRequestSerializer
    pagination_class = StandardResultsSetPagination
    
    @extend_schema(
        summary="List incoming friend requests",
        description="Get all pending friend requests received by you. "
                    "These are requests from other users waiting for your response."
    )
    def get_queryset(self):
        """Get pending friend requests where current user is the recipient"""
        logger.debug(f"User {self.request.user.email} fetching incoming friend requests")
        return FriendService.get_friend_requests(self.request.user)
    
    def list(self, request, *args, **kwargs):
        """Return list of incoming friend requests"""
        queryset = self.filter_queryset(self.get_queryset())
        count = queryset.count()
        
        logger.info(f"User {request.user.email} has {count} incoming friend requests")
        
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return success_response(
            message=f"Found {count} incoming friend request(s)",
            data=serializer.data
        )


@extend_schema(tags=['Friends'])
class SentFriendRequestsAPIView(generics.ListAPIView):
    """
    List all sent (outgoing) friend requests.
    
    GET: Get all pending friend requests sent BY the current user.
    These are requests waiting for the recipient to accept.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = FriendRequestSerializer
    pagination_class = StandardResultsSetPagination
    
    @extend_schema(
        summary="List sent friend requests",
        description="Get all pending friend requests you have sent. "
                    "These are requests waiting for other users to accept."
    )
    def get_queryset(self):
        """Get pending friend requests where current user is the sender"""
        logger.debug(f"User {self.request.user.email} fetching sent friend requests")
        return FriendService.get_sent_requests(self.request.user)
    
    def list(self, request, *args, **kwargs):
        """Return list of sent friend requests"""
        queryset = self.filter_queryset(self.get_queryset())
        count = queryset.count()
        
        logger.info(f"User {request.user.email} has {count} sent friend requests")
        
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return success_response(
            message=f"Found {count} sent friend request(s)",
            data=serializer.data
        )


@extend_schema(tags=['Friends'])
class DeclineFriendRequestAPIView(APIView):
    """
    Decline (reject) a friend request.
    
    POST: Decline a pending friend request sent to you.
    This permanently removes the request - the sender would need to send a new one.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = DeclineFriendSerializer
    
    @extend_schema(
        summary="Decline friend request",
        description="Decline a pending friend request sent to you. "
                    "The request will be permanently deleted.",
        responses={200: dict}
    )
    def post(self, request, pk):
        """Decline a friend request"""
        logger.debug(f"User {request.user.email} attempting to decline friend request {pk}")
        
        # Get the friendship
        try:
            friendship = Friendship.objects.get(id=pk)
        except Friendship.DoesNotExist:
            logger.warning(f"Decline friend request failed: Request {pk} not found")
            return error_response(
                message="Friend request not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Check if current user is the recipient
        if friendship.friend != request.user:
            logger.warning(f"Decline friend request denied: User {request.user.email} is not the recipient of request {pk}")
            return error_response(
                message="You can only decline requests sent to you",
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        # Check if it's still pending
        if friendship.is_accepted():
            logger.warning(f"Decline friend request failed: Request {pk} already accepted")
            return error_response(
                message="Cannot decline an already accepted friend request. Use remove friend instead.",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Store info for logging before deletion
        sender_email = friendship.user.email
        
        # Delete the friend request
        friendship.delete()
        
        logger.info(f"Friend request declined: {sender_email} -> {request.user.email} (Request ID: {pk})")
        
        return success_response(
            message="Friend request declined successfully"
        )


@extend_schema(tags=['Friends'])
class CancelFriendRequestAPIView(APIView):
    """
    Cancel a sent friend request.
    
    POST: Cancel a pending friend request that you sent.
    Use this to withdraw a request before the recipient responds.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = DeclineFriendSerializer
    
    @extend_schema(
        summary="Cancel sent friend request",
        description="Cancel a pending friend request that you sent. "
                    "The request will be permanently deleted.",
        responses={200: dict}
    )
    def post(self, request, pk):
        """Cancel a sent friend request"""
        logger.debug(f"User {request.user.email} attempting to cancel friend request {pk}")
        
        # Get the friendship
        try:
            friendship = Friendship.objects.get(id=pk)
        except Friendship.DoesNotExist:
            logger.warning(f"Cancel friend request failed: Request {pk} not found")
            return error_response(
                message="Friend request not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Check if current user is the sender
        if friendship.user != request.user:
            logger.warning(f"Cancel friend request denied: User {request.user.email} is not the sender of request {pk}")
            return error_response(
                message="You can only cancel requests you sent",
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        # Check if it's still pending
        if friendship.is_accepted():
            logger.warning(f"Cancel friend request failed: Request {pk} already accepted")
            return error_response(
                message="Cannot cancel an already accepted friend request. Use remove friend instead.",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Store info for logging before deletion
        recipient_email = friendship.friend.email
        
        # Delete the friend request
        friendship.delete()
        
        logger.info(f"Friend request cancelled: {request.user.email} -> {recipient_email} (Request ID: {pk})")
        
        return success_response(
            message="Friend request cancelled successfully"
        )
