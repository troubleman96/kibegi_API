from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.db.models import Count
from drf_spectacular.utils import extend_schema, extend_schema_view
from .models import Class, Membership
from .serializers import (
    ClassSerializer, ClassListSerializer, ClassDetailSerializer,
    JoinClassSerializer, MemberSerializer, MembershipSerializer
)
from .services import ClassService
from apps.core.utils.responses import success_response, error_response
from apps.core.pagination import StandardResultsSetPagination
from apps.core.utils.api_cache import build_cache_key, get_cached_response, cache_response, invalidate_cache_namespaces


@extend_schema(tags=['Classes'])
class ClassListCreateAPIView(generics.ListCreateAPIView):
    """List classes or create a new class"""
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ClassSerializer
        return ClassListSerializer
    
    def get_queryset(self):
        """Return classes the user is a member of or public classes"""
        user = self.request.user
        return Class.objects.filter(
            members=user
        ).annotate(total_members=Count('members')).distinct()
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        class_obj = serializer.save()
        invalidate_cache_namespaces('classes', 'search')
        
        return success_response(
            message="Class created successfully",
            data=ClassSerializer(class_obj, context={'request': request}).data,
            status_code=status.HTTP_201_CREATED
        )
    
    def list(self, request, *args, **kwargs):
        cache_key = build_cache_key(request, 'classes')
        cached_response = get_cached_response(cache_key)
        if cached_response is not None:
            return cached_response
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            return cache_response(cache_key, response, 'classes')
        
        serializer = self.get_serializer(queryset, many=True)
        response = success_response(
            message="Classes retrieved successfully",
            data=serializer.data
        )
        return cache_response(cache_key, response, 'classes')


@extend_schema(tags=["Classes"])
class ClassDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a class.
    
    GET: Returns detailed class information including:
    - Basic class details (name, code, creator, etc.)
    - Upload statistics (total uploads, by type, size)
    - Recent uploads (last 10 files)
    - Uploader statistics (who uploaded what, active contributors)
    
    This endpoint is designed to provide rich data for class dashboard UI,
    showing upload activity and making it easy for students to see
    which lecturers are actively sharing materials.
    """
    permission_classes = [IsAuthenticated]
    queryset = Class.objects.all()
    
    def get_serializer_class(self):
        """
        Use ClassDetailSerializer for retrieve (GET) to include uploads info.
        Use ClassSerializer for update (PUT/PATCH) operations.
        """
        if self.request.method == 'GET':
            return ClassDetailSerializer
        return ClassSerializer
    
    def get_object(self):
        obj = super().get_object()
        # Check if user has access to this class
        if not ClassService.user_can_access_class(self.request.user, obj):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You don't have access to this class")
        return obj
    
    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve class details with uploads information.
        
        Returns comprehensive class data including:
        - uploads_summary: Statistics about all uploads in the class
        - recent_uploads: List of 10 most recent uploads
        - uploader_stats: Per-uploader statistics with active contributor flag
        """
        cache_key = build_cache_key(request, 'classes')
        cached_response = get_cached_response(cache_key)
        if cached_response is not None:
            return cached_response
        instance = self.get_object()
        serializer = self.get_serializer(instance, context={'request': request})
        response = success_response(
            message="Class retrieved successfully",
            data=serializer.data
        )
        return cache_response(cache_key, response, 'classes')
    
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Only creator can update
        if instance.creator != request.user:
            return error_response(
                message="Only the class creator can update this class",
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        partial = kwargs.pop('partial', False)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        invalidate_cache_namespaces('classes', 'search')
        
        return success_response(
            message="Class updated successfully",
            data=serializer.data
        )
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Only creator can delete
        if instance.creator != request.user:
            return error_response(
                message="Only the class creator can delete this class",
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        instance.delete()
        invalidate_cache_namespaces('classes', 'search')
        return success_response(
            message="Class deleted successfully",
            status_code=status.HTTP_200_OK
        )


@extend_schema(tags=["Classes"])
class ClassSearchAPIView(generics.ListAPIView):
    """Search for classes"""
    serializer_class = ClassListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        query = self.request.query_params.get('q', '')
        if query:
            return ClassService.search_classes(query, self.request.user)
        return Class.objects.none()
    
    def list(self, request, *args, **kwargs):
        cache_key = build_cache_key(request, 'classes', 'search')
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


@extend_schema(tags=["Classes"])
class JoinClassAPIView(APIView):
    """Join a class using class code"""
    permission_classes = [IsAuthenticated]
    serializer_class = JoinClassSerializer
    
    def post(self, request):
        serializer = JoinClassSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        class_obj = serializer.context['class_obj']
        user = request.user
        
        # Check if already a member
        if class_obj.members.filter(id=user.id).exists():
            return error_response(
                message="You are already a member of this class",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Add user as member
        membership = Membership.objects.create(
            user=user,
            class_obj=class_obj,
            role='student'
        )
        invalidate_cache_namespaces('classes', 'search', 'notifications')

        # Notify class creator/lecturers that someone joined
        try:
            from apps.notifications.services import NotificationService

            joiner_name = getattr(user, "full_name", "Someone")
            class_name = getattr(class_obj, "name", "a class")
            content = f"{joiner_name} joined your class {class_name}"

            lecturer_users = (
                Membership.objects.filter(class_obj=class_obj, role='lecturer')
                .select_related('user')
                .exclude(user=user)
            )
            recipients = {class_obj.creator} if class_obj.creator_id != user.id else set()
            for lecturer_membership in lecturer_users:
                recipients.add(lecturer_membership.user)

            NotificationService.create_bulk(
                [
                    {
                        "user": recipient,
                        "notification_type": "class_joined",
                        "content": content,
                        "related_id": str(class_obj.id),
                    }
                    for recipient in recipients
                ]
            )
        except Exception:
            pass
        
        return success_response(
            message="Successfully joined class",
            data=ClassSerializer(class_obj, context={'request': request}).data
        )


@extend_schema(tags=["Classes"])
class ClassMembersAPIView(generics.ListAPIView):
    """List members of a class"""
    serializer_class = MemberSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        class_id = self.kwargs.get('pk')
        try:
            class_obj = Class.objects.get(pk=class_id)
            
            # Check if user has access
            if not ClassService.user_can_access_class(self.request.user, class_obj):
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("You don't have access to this class")
            
            return class_obj.members.order_by('id')
        except Class.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound("Class not found")
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        class_id = self.kwargs.get('pk')
        try:
            context['class_obj'] = Class.objects.get(pk=class_id)
        except Class.DoesNotExist:
            pass
        return context
    
    def list(self, request, *args, **kwargs):
        cache_key = build_cache_key(request, 'classes')
        cached_response = get_cached_response(cache_key)
        if cached_response is not None:
            return cached_response
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            return cache_response(cache_key, response, 'classes')
        
        serializer = self.get_serializer(queryset, many=True)
        response = success_response(
            message="Class members retrieved successfully",
            data=serializer.data
        )
        return cache_response(cache_key, response, 'classes')


@extend_schema(tags=["Classes"])
class LeaveClassAPIView(APIView):
    """Leave a class"""
    permission_classes = [IsAuthenticated]
    serializer_class = None
    
    def post(self, request, pk):
        try:
            class_obj = Class.objects.get(pk=pk)
        except Class.DoesNotExist:
            return error_response(
                message="Class not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Cannot leave if you're the creator
        if class_obj.creator == request.user:
            return error_response(
                message="Class creator cannot leave the class",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if member
        membership = class_obj.memberships.filter(user=request.user).first()
        if not membership:
            return error_response(
                message="You are not a member of this class",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        membership.delete()
        invalidate_cache_namespaces('classes', 'search')
        return success_response(
            message="Successfully left the class"
        )
