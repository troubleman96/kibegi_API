from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django.db.models import Q
from django.utils import timezone
from django.http import FileResponse, Http404, StreamingHttpResponse
from django.utils.encoding import smart_str
from django.core.files.storage import default_storage
from datetime import timedelta
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
import mimetypes
import os
from .models import Upload
from .serializers import UploadSerializer, UploadListSerializer
from apps.core.utils.responses import success_response, error_response
from apps.core.pagination import StandardResultsSetPagination
from apps.core.utils.api_cache import build_cache_key, get_cached_response, cache_response, invalidate_cache_namespaces


@extend_schema(tags=['Uploads'])
class UploadListCreateAPIView(generics.ListCreateAPIView):
    """List uploads or create a new upload"""
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return UploadSerializer
        return UploadListSerializer
    
    def get_queryset(self):
        """Return non-deleted uploads for the user"""
        user = self.request.user
        queryset = Upload.objects.filter(is_deleted=False)
        
        # Filter by class if provided
        class_id = self.request.query_params.get('class_id')
        if class_id:
            queryset = queryset.filter(class_obj_id=class_id)
        
        # Students see all uploads, lecturers see only their own
        if user.user_type == 'student':
            return queryset
        else:
            return queryset.filter(uploader=user)
    
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

    def create(self, request, *args, **kwargs):
        file_obj = request.FILES.get('file')
        if file_obj and file_obj.size > self.MAX_FILE_SIZE:
            size_mb = file_obj.size / (1024 * 1024)
            return error_response(
                message=f"File too large ({size_mb:.1f} MB). Maximum allowed size is 5 MB.",
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        upload = serializer.save()
        invalidate_cache_namespaces('uploads', 'files', 'storage', 'search', 'classes', 'notifications')

        # Notify other class members about the new upload
        try:
            from apps.notifications.services import NotificationService

            class_obj = upload.class_obj
            uploader = upload.uploader
            recipients = class_obj.members.exclude(id=uploader.id)
            uploader_name = getattr(uploader, "full_name", "Someone")
            file_name = getattr(upload, "file_name", "a file")
            class_name = getattr(class_obj, "name", "your class")
            content = f"{uploader_name} uploaded \"{file_name}\" in {class_name}"

            NotificationService.create_bulk(
                [
                    {
                        "user": member,
                        "notification_type": "upload_created",
                        "content": content,
                        "related_id": str(upload.id),
                    }
                    for member in recipients
                ]
            )
        except Exception:
            pass
        
        return success_response(
            message="File uploaded successfully",
            data=UploadSerializer(upload, context={'request': request}).data,
            status_code=status.HTTP_201_CREATED
        )
    
    def list(self, request, *args, **kwargs):
        cache_key = build_cache_key(request, 'uploads')
        cached_response = get_cached_response(cache_key)
        if cached_response is not None:
            return cached_response
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            return cache_response(cache_key, response, 'uploads')
        
        serializer = self.get_serializer(queryset, many=True)
        response = success_response(
            message="Uploads retrieved successfully",
            data=serializer.data
        )
        return cache_response(cache_key, response, 'uploads')


@extend_schema(tags=["Uploads"])
class UploadDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update or delete an upload by file_code"""
    serializer_class = UploadSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'file_code'
    
    def get_queryset(self):
        """Users can only access non-deleted uploads"""
        return Upload.objects.filter(is_deleted=False)

    def get_object(self):
        instance = super().get_object()
        user = self.request.user

        is_owner = instance.uploader_id == user.id
        is_class_member = instance.class_obj.members.filter(id=user.id).exists()
        has_share_access = instance.shares.filter(shared_with=user, status='accepted').exists()

        if not (is_owner or is_class_member or has_share_access):
            raise PermissionDenied("You don't have permission to access this file")

        return instance
    
    def retrieve(self, request, *args, **kwargs):
        cache_key = build_cache_key(request, 'uploads')
        cached_response = get_cached_response(cache_key)
        if cached_response is not None:
            return cached_response
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        response = success_response(
            message="Upload retrieved successfully",
            data=serializer.data
        )
        return cache_response(cache_key, response, 'uploads')
    
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Only uploader can update
        if instance.uploader != request.user:
            return error_response(
                message="You don't have permission to update this file",
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        partial = kwargs.pop('partial', False)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        invalidate_cache_namespaces('uploads', 'files', 'storage', 'search', 'classes', 'sharing')
        
        return success_response(
            message="Upload updated successfully",
            data=serializer.data
        )
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Only uploader can delete
        if instance.uploader != request.user:
            return error_response(
                message="You don't have permission to delete this file",
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        instance.soft_delete()
        invalidate_cache_namespaces('uploads', 'files', 'storage', 'search', 'classes', 'sharing')
        return success_response(
            message="Upload moved to trash",
            status_code=status.HTTP_200_OK
        )


@extend_schema(tags=["Uploads"])
class TrashAPIView(generics.ListAPIView):
    """List deleted uploads (trash)"""
    serializer_class = UploadListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Return deleted uploads for the user"""
        return Upload.objects.filter(
            uploader=self.request.user,
            is_deleted=True
        )
    
    def list(self, request, *args, **kwargs):
        cache_key = build_cache_key(request, 'uploads', extra='trash')
        cached_response = get_cached_response(cache_key)
        if cached_response is not None:
            return cached_response
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            return cache_response(cache_key, response, 'uploads')
        
        serializer = self.get_serializer(queryset, many=True)
        response = success_response(
            message="Trash retrieved successfully",
            data=serializer.data
        )
        return cache_response(cache_key, response, 'uploads')


@extend_schema(tags=["Uploads"])
class RestoreUploadAPIView(APIView):
    """Restore a deleted upload"""
    permission_classes = [IsAuthenticated]
    serializer_class = UploadSerializer
    
    def post(self, request, pk):
        try:
            upload = Upload.objects.get(pk=pk, uploader=request.user, is_deleted=True)
        except Upload.DoesNotExist:
            return error_response(
                message="Upload not found in trash",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        upload.restore()
        invalidate_cache_namespaces('uploads', 'files', 'storage', 'search', 'classes', 'sharing')
        return success_response(
            message="Upload restored successfully",
            data=UploadSerializer(upload, context={'request': request}).data
        )


@extend_schema(
    summary="Permanently Delete File",
    description="""
    Permanently delete a file from trash (hard delete).
    
    WARNING: This action is irreversible!
    - The file will be permanently removed from the database
    - The physical file will be deleted from storage
    - This action cannot be undone
    
    Requirements:
    - File must be in trash (is_deleted=True)
    - You must be the uploader (owner)
    """,
    parameters=[
        OpenApiParameter(
            name='pk',
            type=OpenApiTypes.UUID,
            location=OpenApiParameter.PATH,
            description='UUID of the file to permanently delete'
        ),
    ],
    responses={
        200: OpenApiResponse(description="File permanently deleted"),
        403: OpenApiResponse(description="Not authorized to delete this file"),
        404: OpenApiResponse(description="File not found in trash"),
    },
    tags=['Uploads']
)
class PermanentDeleteAPIView(APIView):
    """
    Permanently delete a file from trash.
    
    This endpoint performs a hard delete:
    1. Deletes the physical file from storage
    2. Removes the database record
    
    The file must be in trash (soft deleted) first.
    """
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, pk):
        """Permanently delete the file"""
        try:
            upload = Upload.objects.get(pk=pk, uploader=request.user, is_deleted=True)
        except Upload.DoesNotExist:
            return Response(
                error_response("File not found in trash"),
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Store file info before deletion
        file_name = upload.file_name
        storage = upload.file.storage if upload.file else None
        file_name_in_storage = upload.file.name if upload.file else None

        # Delete physical file from storage in a backend-safe way (local, S3, MinIO)
        if storage and file_name_in_storage:
            try:
                storage.delete(file_name_in_storage)
            except Exception as e:
                # Log error but continue with database deletion
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to delete physical file {file_name_in_storage}: {e}")
        
        # Delete database record
        upload.delete()
        invalidate_cache_namespaces('uploads', 'files', 'storage', 'search', 'classes', 'sharing')
        
        return success_response(
            message=f"'{file_name}' permanently deleted",
            status_code=status.HTTP_200_OK
        )


@extend_schema(tags=["Uploads"])
class SearchUploadsAPIView(generics.ListAPIView):
    """Search uploads by filename"""
    serializer_class = UploadListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        query = self.request.query_params.get('q', '')
        user = self.request.user
        
        queryset = Upload.objects.filter(is_deleted=False)
        
        if user.user_type == 'lecturer':
            queryset = queryset.filter(uploader=user)
        
        if query:
            queryset = queryset.filter(
                Q(file_name__icontains=query) | Q(file_code__icontains=query)
            )
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        cache_key = build_cache_key(request, 'uploads', 'search')
        cached_response = get_cached_response(cache_key)
        if cached_response is not None:
            return cached_response
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            return cache_response(cache_key, response, 'search')
        
        serializer = self.get_serializer(queryset, many=True)
        response = success_response(
            message="Search results retrieved successfully",
            data=serializer.data
        )
        return cache_response(cache_key, response, 'search')


@extend_schema(tags=["Uploads"])
class RecentFilesAPIView(generics.ListAPIView):
    """List recent uploads (last 7 days)"""
    serializer_class = UploadListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        user = self.request.user
        seven_days_ago = timezone.now() - timedelta(days=7)
        
        queryset = Upload.objects.filter(
            is_deleted=False,
            created_at__gte=seven_days_ago
        )
        
        if user.user_type == 'lecturer':
            queryset = queryset.filter(uploader=user)
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        cache_key = build_cache_key(request, 'uploads', extra='recent')
        cached_response = get_cached_response(cache_key)
        if cached_response is not None:
            return cached_response
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            return cache_response(cache_key, response, 'uploads')
        
        serializer = self.get_serializer(queryset, many=True)
        response = success_response(
            message="Recent files retrieved successfully",
            data=serializer.data
        )
        return cache_response(cache_key, response, 'uploads')


@extend_schema(
    summary="Download File",
    description="""
    Download a file with proper headers for cross-device compatibility.
    
    Features:
    - Works on PC, mobile, and tablet devices
    - Automatic MIME type detection
    - Downloads with original filename
    - Supports streaming for large files
    - Secure access control
    
    Access Control:
    - Must be authenticated
    - Must be member of file's class OR have accepted share
    """,
    parameters=[
        OpenApiParameter(
            name='file_code',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.PATH,
            description='Unique 8-character file code'
        ),
    ],
    responses={
        200: OpenApiResponse(
            description="File downloaded successfully"
        ),
        403: OpenApiResponse(description="Not authorized to download this file"),
        404: OpenApiResponse(description="File not found or deleted"),
    },
    tags=['Uploads']
)
class DownloadFileAPIView(APIView):
    """
    Download file with proper headers for cross-device access.
    
    This endpoint:
    1. Validates user has access (class member OR accepted share)
    2. Serves file with correct MIME type
    3. Sets proper headers for download
    4. Supports streaming for large files
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, file_code):
        try:
            # Get upload by file_code
            upload = Upload.objects.select_related('class_obj', 'uploader').get(
                file_code=file_code,
                is_deleted=False
            )
        except Upload.DoesNotExist:
            return Response(
                error_response("File not found or has been deleted"),
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check access: Must be class member OR have accepted share
        user = request.user
        from apps.classes.models import Membership
        
        is_class_member = Membership.objects.filter(
            user=user,
            class_obj=upload.class_obj
        ).exists()
        
        # Check if file is shared with user (accepted)
        has_share_access = False
        if not is_class_member:
            try:
                from apps.sharing.models import SharedFile
                has_share_access = SharedFile.objects.filter(
                    upload=upload,
                    shared_with=user,
                    status='accepted'
                ).exists()
            except:
                pass  # Sharing app might not be available
        
        if not (is_class_member or has_share_access):
            return Response(
                error_response("You don't have permission to download this file"),
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Stream file from MinIO/S3 through Django
        # This ensures proper headers and CORS for downloads
        try:
            # Check if file exists in storage
            if not default_storage.exists(upload.file.name):
                return Response(
                    error_response("File not found in storage"),
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Open file from S3/MinIO
            file_handle = default_storage.open(upload.file.name, 'rb')
            
            # Detect MIME type
            mime_type, _ = mimetypes.guess_type(upload.file_name)
            if not mime_type:
                mime_type = 'application/octet-stream'
            
            # Create streaming response with proper headers
            response = FileResponse(
                file_handle,
                content_type=mime_type,
                as_attachment=True,
                filename=smart_str(upload.file_name)
            )
            
            # Set headers for proper download behavior
            response['Content-Length'] = upload.file_size
            response['Content-Disposition'] = f'attachment; filename="{smart_str(upload.file_name)}"'
            response['X-Content-Type-Options'] = 'nosniff'
            response['Cache-Control'] = 'private, max-age=3600'
            
            # CORS headers are handled by django-cors-headers middleware
            return response
            
        except Exception as e:
            return Response(
                error_response(f"Error downloading file: {str(e)}"),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
