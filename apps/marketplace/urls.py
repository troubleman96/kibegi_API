from django.urls import path

from .views import (
    CategoryDetailAPIView,
    CategoryListAPIView,
    ListingDetailAPIView,
    ListingListCreateAPIView,
    MarketplaceOrderDetailAPIView,
    MarketplaceOrderListAPIView,
    MyListingsAPIView,
    PurchaseListingAPIView,
    SearchListingsAPIView,
)

app_name = 'marketplace'

urlpatterns = [
    path('categories/', CategoryListAPIView.as_view(), name='categories'),
    path('categories/<slug:slug>/', CategoryDetailAPIView.as_view(), name='category-detail'),
    path('listings/', ListingListCreateAPIView.as_view(), name='listings'),
    path('listings/search/', SearchListingsAPIView.as_view(), name='listing-search'),
    path('listings/me/', MyListingsAPIView.as_view(), name='my-listings'),
    path('listings/<str:listing_code>/', ListingDetailAPIView.as_view(), name='listing-detail'),
    path('listings/<str:listing_code>/purchase/', PurchaseListingAPIView.as_view(), name='listing-purchase'),
    path('orders/', MarketplaceOrderListAPIView.as_view(), name='orders'),
    path('orders/<uuid:id>/', MarketplaceOrderDetailAPIView.as_view(), name='order-detail'),
]
