from django.db.models import Q
from django.http import FileResponse
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from apps.core.pagination import StandardResultsSetPagination
from apps.core.utils.api_cache import build_cache_key, cache_response, get_cached_response, invalidate_cache_namespaces
from apps.core.utils.responses import error_response, success_response

from .models import LibraryCategory, LibraryItem
from .serializers import LibraryCategorySerializer, LibraryItemListSerializer, LibraryItemSerializer


@extend_schema(tags=['Library'])
class LibraryCategoryListAPIView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = LibraryCategorySerializer
    pagination_class = None

    def get_queryset(self):
        return LibraryCategory.objects.filter(is_active=True)

    def list(self, request, *args, **kwargs):
        cache_key = build_cache_key(request, 'library', 'categories')
        cached_response = get_cached_response(cache_key)
        if cached_response is not None:
            return cached_response
        serializer = self.get_serializer(self.filter_queryset(self.get_queryset()), many=True)
        response = success_response(message='Library categories retrieved successfully', data=serializer.data)
        return cache_response(cache_key, response, 'library')


@extend_schema(tags=['Library'])
class LibraryItemListCreateAPIView(generics.ListCreateAPIView):
    pagination_class = StandardResultsSetPagination

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return LibraryItemSerializer
        return LibraryItemListSerializer

    def get_queryset(self):
        queryset = LibraryItem.objects.select_related('uploaded_by', 'category')
        q = self.request.query_params.get('q')
        category = self.request.query_params.get('category')
        file_type = self.request.query_params.get('file_type')
        featured = self.request.query_params.get('featured')
        subject = self.request.query_params.get('subject')
        course_code = self.request.query_params.get('course_code')

        queryset = queryset.filter(status='public')
        if q:
            queryset = queryset.filter(
                Q(title__icontains=q)
                | Q(description__icontains=q)
                | Q(subject__icontains=q)
                | Q(course_code__icontains=q)
                | Q(author_name__icontains=q)
            )
        if category:
            queryset = queryset.filter(category__slug=category)
        if file_type:
            queryset = queryset.filter(file_type=file_type)
        if featured in ('true', '1', 'yes'):
            queryset = queryset.filter(is_featured=True)
        if subject:
            queryset = queryset.filter(subject__icontains=subject)
        if course_code:
            queryset = queryset.filter(course_code__icontains=course_code)

        return queryset

    def list(self, request, *args, **kwargs):
        cache_key = build_cache_key(request, 'library', 'items')
        cached_response = get_cached_response(cache_key)
        if cached_response is not None:
            return cached_response
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = success_response(
                message='Library items retrieved successfully',
                data=self.get_paginated_response(serializer.data).data,
            )
            return cache_response(cache_key, response, 'library')
        serializer = self.get_serializer(queryset, many=True)
        response = success_response(message='Library items retrieved successfully', data=serializer.data)
        return cache_response(cache_key, response, 'library')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        invalidate_cache_namespaces('library', 'search')
        return success_response(
            message='Library item uploaded successfully',
            data=LibraryItemSerializer(item, context={'request': request}).data,
            status_code=status.HTTP_201_CREATED,
        )


@extend_schema(tags=['Library'])
class LibraryItemDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = LibraryItemSerializer
    lookup_field = 'item_code'

    def get_permissions(self):
        if self.request.method in ('PUT', 'PATCH', 'DELETE'):
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_queryset(self):
        return LibraryItem.objects.select_related('uploaded_by', 'category').filter(status='public')

    def get_object(self):
        instance = super().get_object()
        instance.increment_views()
        return instance

    def retrieve(self, request, *args, **kwargs):
        cache_key = build_cache_key(request, 'library', 'item', kwargs.get('item_code'))
        cached_response = get_cached_response(cache_key)
        if cached_response is not None:
            return cached_response
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        response = success_response(message='Library item retrieved successfully', data=serializer.data)
        return cache_response(cache_key, response, 'library')

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.uploaded_by_id != request.user.id:
            return error_response(message='You do not have permission to update this item.', status_code=status.HTTP_403_FORBIDDEN)
        partial = kwargs.pop('partial', False)
        serializer = self.get_serializer(instance, data=request.data, partial=partial, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        invalidate_cache_namespaces('library', 'search')
        return success_response(message='Library item updated successfully', data=serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.uploaded_by_id != request.user.id:
            return error_response(message='You do not have permission to delete this item.', status_code=status.HTTP_403_FORBIDDEN)
        instance.status = 'archived'
        instance.save(update_fields=['status', 'updated_at'])
        invalidate_cache_namespaces('library', 'search')
        return success_response(message='Library item archived successfully', status_code=status.HTTP_200_OK)


@extend_schema(tags=['Library'])
class MyLibraryItemsAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LibraryItemListSerializer
    pagination_class = None

    def get_queryset(self):
        return LibraryItem.objects.select_related('uploaded_by', 'category').filter(uploaded_by=self.request.user)

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return success_response(message='My library items retrieved successfully', data=serializer.data)


@extend_schema(tags=['Library'])
class SearchLibraryItemsAPIView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = LibraryItemListSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        q = self.request.query_params.get('q', '')
        queryset = LibraryItem.objects.select_related('uploaded_by', 'category').filter(status='public')
        if q:
            queryset = queryset.filter(
                Q(title__icontains=q)
                | Q(description__icontains=q)
                | Q(subject__icontains=q)
                | Q(course_code__icontains=q)
                | Q(author_name__icontains=q)
            )
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return success_response(
                message='Library search results retrieved successfully',
                data=self.get_paginated_response(serializer.data).data,
            )
        serializer = self.get_serializer(queryset, many=True)
        return success_response(message='Library search results retrieved successfully', data=serializer.data)


@extend_schema(tags=['Library'])
class DownloadLibraryItemAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, item_code):
        try:
            item = LibraryItem.objects.get(item_code=item_code, status='public')
        except LibraryItem.DoesNotExist:
            return error_response(message='Library item not found.', status_code=status.HTTP_404_NOT_FOUND)

        item.increment_downloads()
        file_handle = item.file.open('rb')
        response = FileResponse(file_handle, as_attachment=True, filename=item.file_name)
        return response
