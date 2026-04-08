from rest_framework.views import APIView
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import FileResponse, Http404
from django.utils.encoding import smart_str
from django.core.files.storage import default_storage
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
import mimetypes
from .models import SharedFile
from .serializers import (
    ShareFileSerializer, BulkShareSerializer, SharedFileSerializer,
    SharedFileListSerializer, AcceptRejectSerializer
)
from .services import SharingService
from .tasks import create_share_async, bulk_share_async, accept_share_async, reject_share_async
from apps.core.utils.responses import success_response, error_response
from apps.core.pagination import StandardResultsSetPagination
from apps.core.utils.api_cache import build_cache_key, get_cached_response, cache_response, invalidate_cache_namespaces


@extend_schema(tags=['File Sharing'])
class ShareFileAPIView(APIView):
    """
    Share a file with another user.
    
    POST: Create a new file share request.
    The recipient will receive a pending request that they can accept or reject.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ShareFileSerializer
    
    @extend_schema(
        summary="Share a file with a user",
        description="Share one of your uploaded files with another user in the same class. "
                    "Recipient must accept the share to access the file.",
        request=ShareFileSerializer,
        responses={201: SharedFileSerializer}
    )
    def post(self, request):
        """Create a new file share"""
        serializer = ShareFileSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        # Get validated data from context (set during validation)
        upload = serializer.context['upload']
        shared_with = serializer.context['shared_with']
        message = serializer.validated_data.get('message', '')
        
        try:
            # Create the share synchronously first to validate
            share = SharingService.create_share(
                upload=upload,
                shared_by=request.user,
                shared_with=shared_with,
                message=message
            )
            
            # TODO: Trigger async notification in background
            # This prevents blocking if receiver is slow or offline
            # When notifications app is ready, uncomment:
            # from .tasks import notify_share_created_async
            # notify_share_created_async(share)
            
            # Return full share details immediately
            response_serializer = SharedFileSerializer(share)
            invalidate_cache_namespaces('sharing', 'files', 'notifications')
            return success_response(
                message="File shared successfully. Recipient will be notified.",
                data=response_serializer.data,
                status_code=status.HTTP_201_CREATED
            )
        except ValueError as e:
            return error_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST
            )


@extend_schema(tags=['File Sharing'])
class BulkShareAPIView(APIView):
    """
    Share a file with multiple users at once.
    
    POST: Create share requests for multiple users.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = BulkShareSerializer
    
    @extend_schema(
        summary="Share file with multiple users",
        description="Share a file with multiple users in one request. "
                    "Returns success and error lists.",
        request=BulkShareSerializer,
        responses={200: SharedFileSerializer}
    )
    def post(self, request):
        """Share file with multiple users"""
        serializer = BulkShareSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        upload = serializer.context['upload']
        user_ids = serializer.validated_data['user_ids']
        message = serializer.validated_data.get('message', '')
        
        # Process bulk sharing in background to prevent blocking
        # This is especially important when sharing with many users
        bulk_share_async(
            upload=upload,
            shared_by=request.user,
            user_ids=user_ids,
            message=message
        )
        
        # Return immediately without waiting for completion
        return success_response(
            message=f"Sharing with {len(user_ids)} users in progress. Recipients will be notified.",
            data={
                "status": "processing",
                "user_count": len(user_ids),
                "file_code": upload.file_code
            },
            status_code=status.HTTP_202_ACCEPTED
        )


@extend_schema(tags=['File Sharing'])
class ShareRequestListAPIView(generics.ListAPIView):
    """
    List share requests received by the current user.
    
    GET: Get all pending share requests that need action.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = SharedFileListSerializer
    pagination_class = StandardResultsSetPagination
    
    @extend_schema(
        summary="List pending share requests",
        description="Get all pending file share requests sent to you. "
                    "These are awaiting your acceptance or rejection."
    )
    def get_queryset(self):
        """Get pending requests for current user"""
        return SharingService.get_pending_requests(self.request.user)
    
    def list(self, request, *args, **kwargs):
        """Return paginated list of pending requests"""
        cache_key = build_cache_key(request, 'sharing', extra='pending')
        cached_response = get_cached_response(cache_key)
        if cached_response is not None:
            return cached_response
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            return cache_response(cache_key, response, 'sharing')
        
        serializer = self.get_serializer(queryset, many=True)
        response = success_response(
            message="Pending requests retrieved successfully",
            data=serializer.data
        )
        return cache_response(cache_key, response, 'sharing')


@extend_schema(tags=['File Sharing'])
class SharedWithMeAPIView(generics.ListAPIView):
    """
    List all files shared with the current user.
    
    GET: Get accepted shares (files you can access).
    Query param 'status' can filter by pending/accepted/rejected.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = SharedFileListSerializer
    pagination_class = StandardResultsSetPagination
    
    @extend_schema(
        summary="List files shared with me",
        description="Get all files that have been shared with you. "
                    "Filter by status: pending, accepted, or rejected.",
        parameters=[
            {
                'name': 'status',
                'in': 'query',
                'description': 'Filter by share status',
                'required': False,
                'schema': {'type': 'string', 'enum': ['pending', 'accepted', 'rejected']}
            }
        ]
    )
    def get_queryset(self):
        """Get shares received by current user"""
        status_filter = self.request.query_params.get('status')
        return SharingService.get_shared_with_me(
            self.request.user,
            status=status_filter
        )
    
    def list(self, request, *args, **kwargs):
        """Return paginated list of shared files"""
        cache_key = build_cache_key(request, 'sharing', 'files')
        cached_response = get_cached_response(cache_key)
        if cached_response is not None:
            return cached_response
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            return cache_response(cache_key, response, 'sharing')
        
        serializer = self.get_serializer(queryset, many=True)
        response = success_response(
            message="Shared files retrieved successfully",
            data=serializer.data
        )
        return cache_response(cache_key, response, 'sharing')


@extend_schema(tags=['File Sharing'])
class MySharesAPIView(generics.ListAPIView):
    """
    List files I have shared with others.
    
    GET: Get all shares created by current user.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = SharedFileListSerializer
    pagination_class = StandardResultsSetPagination
    
    @extend_schema(
        summary="List files I shared",
        description="Get all files you have shared with other users.",
        parameters=[
            {
                'name': 'status',
                'in': 'query',
                'description': 'Filter by share status',
                'required': False,
                'schema': {'type': 'string', 'enum': ['pending', 'accepted', 'rejected']}
            }
        ]
    )
    def get_queryset(self):
        """Get shares created by current user"""
        status_filter = self.request.query_params.get('status')
        return SharingService.get_my_shares(
            self.request.user,
            status=status_filter
        )
    
    def list(self, request, *args, **kwargs):
        """Return paginated list of user's shares"""
        cache_key = build_cache_key(request, 'sharing', extra='my-shares')
        cached_response = get_cached_response(cache_key)
        if cached_response is not None:
            return cached_response
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            return cache_response(cache_key, response, 'sharing')
        
        serializer = self.get_serializer(queryset, many=True)
        response = success_response(
            message="Your shares retrieved successfully",
            data=serializer.data
        )
        return cache_response(cache_key, response, 'sharing')


@extend_schema(tags=['File Sharing'])
class AcceptShareAPIView(APIView):
    """
    Accept a share request.
    
    POST: Accept a pending share to gain access to the file.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = AcceptRejectSerializer
    
    @extend_schema(
        summary="Accept a share request",
        description="Accept a pending file share. You will then have access to the file.",
        responses={200: SharedFileSerializer}
    )
    def post(self, request, share_id):
        """Accept a share request"""
        # Get share and verify user is the recipient
        share = SharingService.get_share_by_id(share_id, request.user)
        
        if not share:
            return error_response(
                message="Share not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Only recipient can accept
        if share.shared_with != request.user:
            return error_response(
                message="Only the recipient can accept this share",
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        # Check if already accepted
        if share.is_accepted():
            return error_response(
                message="Share already accepted",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Accept the share immediately
        share.accept()
        invalidate_cache_namespaces('sharing', 'files', 'notifications')
        
        # Trigger async notification to sharer in background
        # This prevents blocking if sharer is offline
        # TODO: When notifications app is ready:
        # from .tasks import notify_share_accepted_async
        # notify_share_accepted_async(share)
        
        # Return updated share details
        serializer = SharedFileSerializer(share)
        return success_response(
            message="Share accepted successfully. You can now access the file.",
            data=serializer.data
        )


@extend_schema(tags=['File Sharing'])
class RejectShareAPIView(APIView):
    """
    Reject a share request.
    
    POST: Reject a pending share request.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = AcceptRejectSerializer
    
    @extend_schema(
        summary="Reject a share request",
        description="Reject a pending file share request.",
        responses={200: SharedFileSerializer}
    )
    def post(self, request, share_id):
        """Reject a share request"""
        # Get share and verify user is the recipient
        share = SharingService.get_share_by_id(share_id, request.user)
        
        if not share:
            return error_response(
                message="Share not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Only recipient can reject
        if share.shared_with != request.user:
            return error_response(
                message="Only the recipient can reject this share",
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        # Check if already rejected
        if share.is_rejected():
            return error_response(
                message="Share already rejected",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Reject the share immediately
        share.reject()
        invalidate_cache_namespaces('sharing', 'files', 'notifications')
        
        # Trigger async notification to sharer in background
        # This prevents blocking if sharer is offline
        # TODO: When notifications app is ready:
        # from .tasks import notify_share_rejected_async
        # notify_share_rejected_async(share)
        
        # Return updated share details
        serializer = SharedFileSerializer(share)
        return success_response(
            message="Share rejected",
            data=serializer.data
        )


@extend_schema(tags=['File Sharing'])
class ShareDetailAPIView(generics.RetrieveAPIView):
    """
    Get details of a specific share.
    
    GET: Retrieve full details of a share you're involved in.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = SharedFileSerializer
    lookup_field = 'id'
    lookup_url_kwarg = 'share_id'
    
    @extend_schema(
        summary="Get share details",
        description="Get detailed information about a specific file share."
    )
    def get_object(self):
        """Get share ensuring user has access"""
        share_id = self.kwargs.get('share_id')
        share = SharingService.get_share_by_id(share_id, self.request.user)
        
        if not share:
            from rest_framework.exceptions import NotFound
            raise NotFound("Share not found")
        
        return share
    
    def retrieve(self, request, *args, **kwargs):
        """Return share details"""
        cache_key = build_cache_key(request, 'sharing')
        cached_response = get_cached_response(cache_key)
        if cached_response is not None:
            return cached_response
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        response = success_response(
            message="Share details retrieved successfully",
            data=serializer.data
        )
        return cache_response(cache_key, response, 'sharing')


@extend_schema(
    summary="Download Shared File",
    description="""
    Download a file that has been shared with you.
    
    Requirements:
    - Share must be accepted (status = 'accepted')
    - You must be the recipient of the share
    
    Features:
    - Works on PC, mobile, and tablet devices
    - Automatic MIME type detection
    - Downloads with original filename
    - Supports streaming for large files
    - Secure access control
    """,
    parameters=[
        OpenApiParameter(
            name='share_id',
            type=OpenApiTypes.UUID,
            location=OpenApiParameter.PATH,
            description='UUID of the share'
        ),
    ],
    responses={
        200: OpenApiResponse(
            description="File downloaded successfully"
        ),
        403: OpenApiResponse(description="Share not accepted or not authorized"),
        404: OpenApiResponse(description="Share not found"),
    },
    tags=['File Sharing']
)
class DownloadSharedFileAPIView(APIView):
    """
    Download a file that has been shared with you.
    
    This endpoint allows recipients to download files that have been
    shared with them and accepted. The share must have status='accepted'.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, share_id):
        """Download the shared file"""
        try:
            # Get the share
            share = SharedFile.objects.select_related(
                'upload', 'shared_by', 'shared_with'
            ).get(id=share_id)
        except SharedFile.DoesNotExist:
            return Response(
                error_response("Share not found"),
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verify user is the recipient
        if share.shared_with != request.user:
            return Response(
                error_response("You are not authorized to download this file"),
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Verify share is accepted
        if share.status != 'accepted':
            return Response(
                error_response("Share must be accepted before downloading. Current status: " + share.status),
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get the upload
        upload = share.upload
        
        # Check if file exists and is not deleted
        if upload.is_deleted:
            return Response(
                error_response("This file has been deleted by the owner"),
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if file exists in the configured storage backend
        if not default_storage.exists(upload.file.name):
            return Response(
                error_response("File not found in storage"),
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Detect MIME type
        mime_type, _ = mimetypes.guess_type(upload.file.name)
        if not mime_type:
            mime_type = 'application/octet-stream'
        
        # Open file for reading
        try:
            file_handle = default_storage.open(upload.file.name, 'rb')
        except IOError:
            return Response(
                error_response("Error opening file"),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Create response with proper headers
        response = FileResponse(
            file_handle,
            content_type=mime_type,
            as_attachment=True,
            filename=smart_str(upload.file_name)
        )
        
        # Set additional headers for better compatibility
        response['Content-Length'] = upload.file_size
        response['Content-Disposition'] = f'attachment; filename="{smart_str(upload.file_name)}"'
        response['X-Content-Type-Options'] = 'nosniff'
        response['Cache-Control'] = 'private, max-age=3600'
        
        return response
