"""
Storage App Views

This module defines API views for storage management.
All endpoints require authentication.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from .models import UserStorage, StorageUsageHistory
from .serializers import (
    UserStorageSerializer,
    StorageInfoSerializer,
    StorageUsageHistorySerializer
)
from .services import StorageService
from core.utils.responses import success_response, error_response


class UserStorageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing user storage information.
    
    This ViewSet provides:
    - GET /api/v1/storage/ - Get current user's storage info
    - GET /api/v1/storage/info/ - Get detailed storage information
    - GET /api/v1/storage/history/ - Get storage usage history
    """
    
    permission_classes = [IsAuthenticated]
    serializer_class = UserStorageSerializer
    pagination_class = None  # Disable pagination for list endpoint
    
    def get_queryset(self):
        """
        Get queryset filtered to current user's storage.
        
        Returns:
            QuerySet: Storage records for the current user
        """
        return UserStorage.objects.filter(user=self.request.user)
    
    def list(self, request, *args, **kwargs):
        """
        Get current user's storage information.
        
        This endpoint:
        1. Gets or creates storage record for the user
        2. Updates storage calculation
        3. Returns storage information
        
        Returns:
            Response: Storage information with success status
        """
        try:
            # Get or create storage record and update it
            storage = StorageService.update_user_storage(request.user, recalculate=True)
            
            # Serialize the storage data
            serializer = self.get_serializer(storage)
            
            # Get the serialized data as a plain dict
            data = dict(serializer.data)
            
            # Return response directly - success_response returns a Response object
            # Make sure data is a plain dict/list, not a Response object
            return success_response(
                message="Storage information retrieved successfully",
                data=data
            )
        
        except Exception as e:
            # Return error response directly
            return error_response(
                message="Failed to retrieve storage information",
                errors={"detail": str(e)},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], url_path='info')
    def storage_info(self, request):
        """
        Get detailed storage information for the current user.
        
        This endpoint provides a comprehensive summary of storage usage
        in a user-friendly format.
        
        Returns:
            Response: Detailed storage information including:
                - Total quota
                - Used storage
                - Free storage
                - Usage percentage
                - Status flags (is_full, is_near_limit)
        """
        try:
            # Get comprehensive storage information
            storage_info = StorageService.get_storage_info(request.user)
            
            # Serialize the information
            serializer = StorageInfoSerializer(storage_info)
            
            # success_response already returns a Response object, so return it directly
            return success_response(
                message="Storage information retrieved successfully",
                data=serializer.data
            )
        
        except Exception as e:
            # error_response already returns a Response object, so return it directly
            return error_response(
                message="Failed to retrieve storage information",
                errors={"detail": str(e)},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'], url_path='recalculate')
    def recalculate_storage(self, request):
        """
        Manually trigger storage recalculation.
        
        This endpoint forces a recalculation of storage usage
        from all uploaded files. Useful if storage seems incorrect.
        
        Returns:
            Response: Updated storage information
        """
        try:
            # Force recalculation
            storage = StorageService.update_user_storage(request.user, recalculate=True)
            
            # Get updated info
            storage_info = StorageService.get_storage_info(request.user)
            serializer = StorageInfoSerializer(storage_info)
            
            # success_response already returns a Response object, so return it directly
            return success_response(
                message="Storage recalculated successfully",
                data=serializer.data
            )
        
        except Exception as e:
            # error_response already returns a Response object, so return it directly
            return error_response(
                message="Failed to recalculate storage",
                errors={"detail": str(e)},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], url_path='history')
    def usage_history(self, request):
        """
        Get storage usage history for the current user.
        
        This endpoint returns historical snapshots of storage usage,
        useful for tracking storage growth over time.
        
        Query Parameters:
            limit: Number of records to return (default: 30)
        
        Returns:
            Response: List of storage usage history records
        """
        try:
            # Get storage record
            storage = StorageService.get_or_create_user_storage(request.user)
            
            # Get history records
            limit = int(request.query_params.get('limit', 30))
            history = StorageUsageHistory.objects.filter(
                user_storage=storage
            ).order_by('-recorded_at')[:limit]
            
            # Serialize history
            serializer = StorageUsageHistorySerializer(history, many=True)
            
            # success_response already returns a Response object, so return it directly
            return success_response(
                message="Storage history retrieved successfully",
                data=serializer.data
            )
        
        except Exception as e:
            # error_response already returns a Response object, so return it directly
            return error_response(
                message="Failed to retrieve storage history",
                errors={"detail": str(e)},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
