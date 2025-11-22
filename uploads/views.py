from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from drf_spectacular.utils import extend_schema, extend_schema_view
from .models import Upload
from .serializers import UploadSerializer, UploadListSerializer
from core.utils.responses import success_response, error_response
from core.pagination import StandardResultsSetPagination


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
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        upload = serializer.save()
        
        return success_response(
            message="File uploaded successfully",
            data=UploadSerializer(upload, context={'request': request}).data,
            status_code=status.HTTP_201_CREATED
        )
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return success_response(
            message="Uploads retrieved successfully",
            data=serializer.data
        )


@extend_schema(tags=["Uploads"])
class UploadDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update or delete an upload by file_code"""
    serializer_class = UploadSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'file_code'
    
    def get_queryset(self):
        """Users can only access non-deleted uploads"""
        return Upload.objects.filter(is_deleted=False)
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return success_response(
            message="Upload retrieved successfully",
            data=serializer.data
        )
    
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
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return success_response(
            message="Trash retrieved successfully",
            data=serializer.data
        )


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
        return success_response(
            message="Upload restored successfully",
            data=UploadSerializer(upload, context={'request': request}).data
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
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return success_response(
            message="Search results retrieved successfully",
            data=serializer.data
        )


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
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return success_response(
            message="Recent files retrieved successfully",
            data=serializer.data
        )
