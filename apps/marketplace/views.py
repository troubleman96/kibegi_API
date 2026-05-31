from django.db import transaction
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.core.pagination import StandardResultsSetPagination
from apps.core.utils.api_cache import build_cache_key, cache_response, get_cached_response, invalidate_cache_namespaces
from apps.core.utils.responses import error_response, success_response

from .models import Category, Listing, ListingOrder
from .serializers import (
    CategorySerializer,
    ListingListSerializer,
    ListingOrderSerializer,
    ListingPurchaseSerializer,
    ListingSerializer,
)


@extend_schema(tags=['Marketplace'])
class CategoryListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CategorySerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return Category.objects.filter(is_active=True)

    def list(self, request, *args, **kwargs):
        cache_key = build_cache_key(request, 'marketplace', 'categories')
        cached_response = get_cached_response(cache_key)
        if cached_response is not None:
            return cached_response
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        response = success_response(message='Categories retrieved successfully', data=serializer.data)
        return cache_response(cache_key, response, 'marketplace')


@extend_schema(tags=['Marketplace'])
class CategoryDetailAPIView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CategorySerializer
    lookup_field = 'slug'
    queryset = Category.objects.filter(is_active=True)


@extend_schema(tags=['Marketplace'])
class ListingListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ListingSerializer
        return ListingListSerializer

    def get_queryset(self):
        queryset = Listing.objects.select_related('seller', 'category').all()
        user = self.request.user

        if user.is_authenticated:
            queryset = queryset.exclude(status='archived')
        else:
            queryset = queryset.filter(status='active')

        q = self.request.query_params.get('q')
        category = self.request.query_params.get('category')
        seller_id = self.request.query_params.get('seller_id')
        status_filter = self.request.query_params.get('status')
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')

        if q:
            queryset = queryset.filter(
                Q(title__icontains=q)
                | Q(description__icontains=q)
                | Q(listing_code__icontains=q)
                | Q(location__icontains=q)
            )
        if category:
            queryset = queryset.filter(category__slug=category)
        if seller_id:
            queryset = queryset.filter(seller_id=seller_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        else:
            queryset = queryset.filter(status__in=['active', 'sold_out'])
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)

        return queryset

    def list(self, request, *args, **kwargs):
        cache_key = build_cache_key(request, 'marketplace', 'listings')
        cached_response = get_cached_response(cache_key)
        if cached_response is not None:
            return cached_response
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            return cache_response(cache_key, response, 'marketplace')
        serializer = self.get_serializer(queryset, many=True)
        response = success_response(message='Listings retrieved successfully', data=serializer.data)
        return cache_response(cache_key, response, 'marketplace')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        listing = serializer.save()
        invalidate_cache_namespaces('marketplace', 'notifications', 'search')
        return success_response(
            message='Listing created successfully',
            data=ListingSerializer(listing, context={'request': request}).data,
            status_code=status.HTTP_201_CREATED,
        )


@extend_schema(tags=['Marketplace'])
class ListingDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ListingSerializer
    lookup_field = 'listing_code'

    def get_queryset(self):
        return Listing.objects.select_related('seller', 'category')

    def get_object(self):
        instance = super().get_object()
        user = self.request.user
        has_purchase = instance.orders.filter(buyer=user, status='completed').exists()
        if instance.status == 'archived' and instance.seller_id != user.id and not has_purchase:
            raise PermissionDenied('You do not have access to this listing.')
        return instance

    def retrieve(self, request, *args, **kwargs):
        cache_key = build_cache_key(request, 'marketplace', 'listing', kwargs.get('listing_code'))
        cached_response = get_cached_response(cache_key)
        if cached_response is not None:
            return cached_response
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        response = success_response(message='Listing retrieved successfully', data=serializer.data)
        return cache_response(cache_key, response, 'marketplace')

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.seller_id != request.user.id:
            return error_response(message='You do not have permission to update this listing.', status_code=status.HTTP_403_FORBIDDEN)
        partial = kwargs.pop('partial', False)
        serializer = self.get_serializer(instance, data=request.data, partial=partial, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        invalidate_cache_namespaces('marketplace', 'notifications', 'search')
        return success_response(message='Listing updated successfully', data=serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.seller_id != request.user.id:
            return error_response(message='You do not have permission to delete this listing.', status_code=status.HTTP_403_FORBIDDEN)
        instance.status = 'archived'
        instance.save(update_fields=['status', 'updated_at'])
        invalidate_cache_namespaces('marketplace', 'notifications', 'search')
        return success_response(message='Listing archived successfully', status_code=status.HTTP_200_OK)


@extend_schema(tags=['Marketplace'])
class MyListingsAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ListingListSerializer
    pagination_class = None

    def get_queryset(self):
        return Listing.objects.select_related('seller', 'category').filter(seller=self.request.user)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            payload = self.get_paginated_response(serializer.data).data
            return success_response(message='Listings retrieved successfully', data=payload)

        serializer = self.get_serializer(queryset, many=True)
        return success_response(message='Listings retrieved successfully', data=serializer.data)


@extend_schema(tags=['Marketplace'])
class SearchListingsAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ListingListSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        query = self.request.query_params.get('q', '')
        queryset = Listing.objects.select_related('seller', 'category').filter(status__in=['active', 'sold_out'])
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(listing_code__icontains=query)
                | Q(location__icontains=query)
                | Q(category__name__icontains=query)
            )
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            payload = self.get_paginated_response(serializer.data).data
            return success_response(message='Search results retrieved successfully', data=payload)

        serializer = self.get_serializer(queryset, many=True)
        return success_response(message='Search results retrieved successfully', data=serializer.data)


@extend_schema(tags=['Marketplace'])
class PurchaseListingAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, listing_code):
        serializer = ListingPurchaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        quantity = serializer.validated_data['quantity']

        try:
            listing = Listing.objects.select_for_update().select_related('seller', 'category').get(listing_code=listing_code)
        except Listing.DoesNotExist:
            return error_response(message='Listing not found.', status_code=status.HTTP_404_NOT_FOUND)

        if listing.seller_id == request.user.id:
            return error_response(message='You cannot buy your own listing.', status_code=status.HTTP_400_BAD_REQUEST)
        if listing.status != 'active':
            return error_response(message='This listing is not available for purchase.', status_code=status.HTTP_400_BAD_REQUEST)
        if not listing.can_purchase(quantity):
            return error_response(message='Not enough quantity available.', status_code=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            listing = Listing.objects.select_for_update().get(pk=listing.pk)
            if not listing.can_purchase(quantity):
                return error_response(message='Not enough quantity available.', status_code=status.HTTP_400_BAD_REQUEST)

            order = ListingOrder.objects.create(
                listing=listing,
                buyer=request.user,
                seller=listing.seller,
                quantity=quantity,
                unit_price=listing.price,
                total_price=listing.price * quantity,
                status='completed',
            )
            listing.record_purchase(quantity)

        try:
            from apps.notifications.services import NotificationService

            content = f'{request.user.full_name} bought {quantity} item(s) from your listing "{listing.title}"'
            NotificationService.create_notification(
                user=listing.seller,
                notification_type='marketplace_purchase',
                content=content,
                related_id=str(order.id),
            )
        except Exception:
            pass

        invalidate_cache_namespaces('marketplace', 'notifications', 'search')
        return success_response(
            message='Purchase completed successfully',
            data=ListingOrderSerializer(order, context={'request': request}).data,
            status_code=status.HTTP_201_CREATED,
        )


@extend_schema(tags=['Marketplace'])
class MarketplaceOrderListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ListingOrderSerializer
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        order_type = self.request.query_params.get('type')
        queryset = ListingOrder.objects.select_related('listing', 'listing__seller', 'listing__category', 'buyer', 'seller')
        if order_type == 'sales':
            queryset = queryset.filter(seller=user)
        elif order_type == 'purchases':
            queryset = queryset.filter(buyer=user)
        else:
            queryset = queryset.filter(Q(buyer=user) | Q(seller=user))
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            payload = self.get_paginated_response(serializer.data).data
            return success_response(message='Orders retrieved successfully', data=payload)

        serializer = self.get_serializer(queryset, many=True)
        return success_response(message='Orders retrieved successfully', data=serializer.data)


@extend_schema(tags=['Marketplace'])
class MarketplaceOrderDetailAPIView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ListingOrderSerializer
    lookup_field = 'id'

    def get_queryset(self):
        user = self.request.user
        return ListingOrder.objects.select_related('listing', 'listing__seller', 'listing__category', 'buyer', 'seller').filter(
            Q(buyer=user) | Q(seller=user)
        )
