from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from apps.uploads.models import Upload
from apps.sharing.models import SharedFile
from .serializers import UnifiedFileSerializer, DeletedFileSerializer
from apps.core.utils.responses import success_response, error_response


class AllFilesAPIView(APIView):
    """
    Get all files (uploads + accepted shared files) for the authenticated user.
    Combines files from uploads app and sharing app into a unified view.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get all files",
        description="Returns all files available to the user: their uploads and accepted shared files (excluding deleted files)",
        responses={200: UnifiedFileSerializer(many=True)},
        tags=['Files']
    )
    def get(self, request):
        user = request.user
        files_data = []

        # Get user's uploads (not deleted)
        uploads = Upload.objects.filter(
            uploader=user,
            is_deleted=False
        ).select_related('uploader').order_by('-created_at')

        for upload in uploads:
            files_data.append({
                'id': upload.id,
                'file_code': upload.file_code,
                'file_name': upload.file_name,
                'file_size': upload.file_size,
                'file_type': upload.file_type,
                'file': upload.file,
                'source': 'upload',
                'owner': upload.uploader,
                'uploaded_at': upload.created_at,
                'is_deleted': upload.is_deleted,
                'deleted_at': upload.deleted_at,
                'shared_by': None,
                'shared_at': None,
                'accepted': None,
            })

        # Get shared files (accepted only, not deleted)
        shared_files = SharedFile.objects.filter(
            shared_with=user,
            status='accepted',
            upload__is_deleted=False
        ).select_related('upload', 'upload__uploader', 'shared_by').order_by('-shared_at')

        for shared in shared_files:
            if shared.upload:  # Ensure upload exists
                files_data.append({
                    'id': shared.id,
                    'file_code': shared.upload.file_code,
                    'file_name': shared.upload.file_name,
                    'file_size': shared.upload.file_size,
                    'file_type': shared.upload.file_type,
                    'file': shared.upload.file,
                    'source': 'shared',
                    'owner': shared.upload.uploader,
                    'uploaded_at': shared.upload.created_at,
                    'is_deleted': shared.upload.is_deleted,
                    'deleted_at': shared.upload.deleted_at,
                    'shared_by': shared.shared_by,
                    'shared_at': shared.shared_at,
                    'accepted': True,
                })

        serializer = UnifiedFileSerializer(files_data, many=True, context={'request': request})
        return success_response(
            data=serializer.data,
            message=f"Retrieved {len(files_data)} files"
        )


class MyUploadsAPIView(APIView):
    """
    Get all files uploaded by the authenticated user (from uploads app only).
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get my uploads",
        description="Returns all files uploaded by the authenticated user (excluding deleted files)",
        responses={200: UnifiedFileSerializer(many=True)},
        tags=['Files']
    )
    def get(self, request):
        user = request.user
        
        uploads = Upload.objects.filter(
            uploader=user,
            is_deleted=False
        ).select_related('uploader').order_by('-created_at')

        files_data = []
        for upload in uploads:
            files_data.append({
                'id': upload.id,
                'file_code': upload.file_code,
                'file_name': upload.file_name,
                'file_size': upload.file_size,
                'file_type': upload.file_type,
                'file': upload.file,
                'source': 'upload',
                'owner': upload.uploader,
                'uploaded_at': upload.created_at,
                'is_deleted': upload.is_deleted,
                'deleted_at': upload.deleted_at,
                'shared_by': None,
                'shared_at': None,
                'accepted': None,
            })

        serializer = UnifiedFileSerializer(files_data, many=True, context={'request': request})
        return success_response(
            data=serializer.data,
            message=f"Retrieved {len(files_data)} uploads"
        )


class SharedWithMeAPIView(APIView):
    """
    Get all files shared with the authenticated user (from sharing app only).
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get files shared with me",
        description="Returns all files shared with the authenticated user (accepted only, excluding deleted files)",
        responses={200: UnifiedFileSerializer(many=True)},
        tags=['Files']
    )
    def get(self, request):
        user = request.user

        shared_files = SharedFile.objects.filter(
            shared_with=user,
            status='accepted',
            upload__is_deleted=False
        ).select_related('upload', 'upload__uploader', 'shared_by').order_by('-shared_at')

        files_data = []
        for shared in shared_files:
            if shared.upload:
                files_data.append({
                    'id': shared.id,
                    'file_code': shared.upload.file_code,
                    'file_name': shared.upload.file_name,
                    'file_size': shared.upload.file_size,
                    'file_type': shared.upload.file_type,
                    'file': shared.upload.file,
                    'source': 'shared',
                    'owner': shared.upload.uploader,
                    'uploaded_at': shared.upload.created_at,
                    'is_deleted': shared.upload.is_deleted,
                    'deleted_at': shared.upload.deleted_at,
                    'shared_by': shared.shared_by,
                    'shared_at': shared.shared_at,
                    'accepted': True,
                })

        serializer = UnifiedFileSerializer(files_data, many=True, context={'request': request})
        return success_response(
            data=serializer.data,
            message=f"Retrieved {len(files_data)} shared files"
        )


class DeletedFilesAPIView(APIView):
    """
    Get all deleted files (from both uploads and sharing).
    Shows files in trash that can still be restored within 21 days.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get deleted files",
        description="Returns all deleted files from uploads and sharing (files in trash within 21-day retention period)",
        responses={200: DeletedFileSerializer(many=True)},
        tags=['Files']
    )
    def get(self, request):
        user = request.user
        deleted_files_data = []
        now = timezone.now()

        # Get deleted uploads
        deleted_uploads = Upload.objects.filter(
            uploader=user,
            is_deleted=True
        ).select_related('uploader').order_by('-deleted_at')

        for upload in deleted_uploads:
            days_remaining = 21
            if upload.deleted_at:
                days_passed = (now - upload.deleted_at).days
                days_remaining = max(0, 21 - days_passed)

            deleted_files_data.append({
                'id': upload.id,
                'file_code': upload.file_code,
                'file_name': upload.file_name,
                'file_size': upload.file_size,
                'file_type': upload.file_type,
                'source': 'upload',
                'owner': upload.uploader,
                'deleted_at': upload.deleted_at,
                'days_until_permanent_deletion': days_remaining,
                'shared_by': None,
                'was_accepted': None,
            })

        # Get deleted shared files (where the upload itself is deleted)
        deleted_shared = SharedFile.objects.filter(
            shared_with=user,
            upload__is_deleted=True
        ).select_related('upload', 'upload__uploader', 'shared_by').order_by('-upload__deleted_at')

        for shared in deleted_shared:
            if shared.upload:
                days_remaining = 21
                if shared.upload.deleted_at:
                    days_passed = (now - shared.upload.deleted_at).days
                    days_remaining = max(0, 21 - days_passed)

                deleted_files_data.append({
                    'id': shared.id,
                    'file_code': shared.upload.file_code,
                    'file_name': shared.upload.file_name,
                    'file_size': shared.upload.file_size,
                    'file_type': shared.upload.file_type,
                    'source': 'shared',
                    'owner': shared.upload.uploader,
                    'deleted_at': shared.upload.deleted_at,
                    'days_until_permanent_deletion': days_remaining,
                    'shared_by': shared.shared_by,
                    'was_accepted': shared.status == 'accepted',
                })

        serializer = DeletedFileSerializer(deleted_files_data, many=True, context={'request': request})
        return success_response(
            data=serializer.data,
            message=f"Retrieved {len(deleted_files_data)} deleted files"
        )


class SingleFileDetailAPIView(APIView):
    """
    Get detailed information about a single file by file_code.
    Searches in both uploads and sharing.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get single file details",
        description="Returns detailed information about a specific file (searches both uploads and shared files)",
        parameters=[
            OpenApiParameter(
                name='file_code',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description='Unique file code'
            )
        ],
        responses={
            200: UnifiedFileSerializer,
            404: OpenApiTypes.OBJECT
        },
        tags=['Files']
    )
    def get(self, request, file_code):
        user = request.user

        # First, try to find in uploads
        try:
            upload = Upload.objects.get(
                file_code=file_code,
                uploader=user
            )
            
            file_data = {
                'id': upload.id,
                'file_code': upload.file_code,
                'file_name': upload.file_name,
                'file_size': upload.file_size,
                'file_type': upload.file_type,
                'file': upload.file,
                'source': 'upload',
                'owner': upload.uploader,
                'uploaded_at': upload.created_at,
                'is_deleted': upload.is_deleted,
                'deleted_at': upload.deleted_at,
                'shared_by': None,
                'shared_at': None,
                'accepted': None,
            }
            
            serializer = UnifiedFileSerializer(file_data, context={'request': request})
            return success_response(
                data=serializer.data,
                message="File found in uploads"
            )
        
        except Upload.DoesNotExist:
            pass

        # If not found in uploads, search in shared files
        try:
            shared = SharedFile.objects.select_related('upload', 'upload__uploader', 'shared_by').get(
                upload__file_code=file_code,
                shared_with=user,
                status='accepted'
            )
            
            if shared.upload:
                file_data = {
                    'id': shared.id,
                    'file_code': shared.upload.file_code,
                    'file_name': shared.upload.file_name,
                    'file_size': shared.upload.file_size,
                    'file_type': shared.upload.file_type,
                    'file': shared.upload.file,
                    'source': 'shared',
                    'owner': shared.upload.uploader,
                    'uploaded_at': shared.upload.created_at,
                    'is_deleted': shared.upload.is_deleted,
                    'deleted_at': shared.upload.deleted_at,
                    'shared_by': shared.shared_by,
                    'shared_at': shared.shared_at,
                    'accepted': True,
                }
                
                serializer = UnifiedFileSerializer(file_data, context={'request': request})
                return success_response(
                    data=serializer.data,
                    message="File found in shared files"
                )
        
        except SharedFile.DoesNotExist:
            pass

        return error_response(
            message="File not found",
            status_code=status.HTTP_404_NOT_FOUND
        )


class PermanentDeleteFileAPIView(APIView):
    """
    Permanently delete a file by file_code.
    Works for both uploads and shared files.
    
    - For uploads: Must be the uploader, file must be in trash
    - For shared files: Removes the share (doesn't delete original file)
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Permanently delete file",
        description="""
        Permanently delete a file by file_code.
        
        For YOUR uploads:
        - File must be in trash (soft deleted)
        - Permanently deletes the physical file and database record
        - WARNING: This is irreversible!
        
        For SHARED files:
        - Removes the shared file from your view permanently
        - Original file remains with the owner
        """,
        parameters=[
            OpenApiParameter(
                name='file_code',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description='Unique file code'
            )
        ],
        responses={
            200: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        },
        tags=['Files']
    )
    def delete(self, request, file_code):
        user = request.user
        import logging
        logger = logging.getLogger(__name__)

        # First, check if it's user's upload
        try:
            upload = Upload.objects.get(
                file_code=file_code,
                uploader=user,
                is_deleted=True  # Must be in trash
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
                    logger.error(f"Failed to delete physical file {file_name_in_storage}: {e}")
            
            # Delete database record
            upload.delete()
            
            return success_response(
                message=f"'{file_name}' permanently deleted",
                status_code=status.HTTP_200_OK
            )
        
        except Upload.DoesNotExist:
            pass

        # If not user's upload, check if it's a shared file
        try:
            shared = SharedFile.objects.select_related('upload').get(
                upload__file_code=file_code,
                shared_with=user
            )
            
            file_name = shared.upload.file_name if shared.upload else "File"
            
            # Delete the share record (not the original file)
            shared.delete()
            
            return success_response(
                message=f"'{file_name}' removed from your files",
                status_code=status.HTTP_200_OK
            )
        
        except SharedFile.DoesNotExist:
            pass

        return error_response(
            message="File not found or not in trash",
            status_code=status.HTTP_404_NOT_FOUND
        )


class RestoreFileAPIView(APIView):
    """
    Restore a deleted file by file_code.
    Works for both uploads and shared files.
    
    - For uploads: Restores from trash (soft delete reversal)
    - For shared files: Not applicable (they don't have trash)
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Restore file from trash",
        description="""
        Restore a deleted file by file_code.
        
        For YOUR uploads:
        - File must be in trash (soft deleted)
        - Restores the file (reverses soft delete)
        - File becomes accessible again
        
        For SHARED files:
        - Shared files don't have trash functionality
        - Returns 404 if trying to restore a shared file
        """,
        parameters=[
            OpenApiParameter(
                name='file_code',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description='Unique file code'
            )
        ],
        responses={
            200: UnifiedFileSerializer,
            404: OpenApiTypes.OBJECT
        },
        tags=['Files']
    )
    def post(self, request, file_code):
        user = request.user

        # Only uploads can be restored (they have trash functionality)
        try:
            upload = Upload.objects.get(
                file_code=file_code,
                uploader=user,
                is_deleted=True  # Must be in trash
            )
            
            # Restore the upload
            upload.restore()
            
            # Prepare response data
            file_data = {
                'id': upload.id,
                'file_code': upload.file_code,
                'file_name': upload.file_name,
                'file_size': upload.file_size,
                'file_type': upload.file_type,
                'file': upload.file,
                'source': 'upload',
                'owner': upload.uploader,
                'uploaded_at': upload.created_at,
                'is_deleted': upload.is_deleted,
                'deleted_at': upload.deleted_at,
                'shared_by': None,
                'shared_at': None,
                'accepted': None,
            }
            
            serializer = UnifiedFileSerializer(file_data, context={'request': request})
            return success_response(
                message=f"'{upload.file_name}' restored successfully",
                data=serializer.data
            )
        
        except Upload.DoesNotExist:
            return error_response(
                message="File not found in trash or not an upload",
                status_code=status.HTTP_404_NOT_FOUND
            )
