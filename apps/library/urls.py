from django.urls import path

from .views import (
    DownloadLibraryItemAPIView,
    LibraryCategoryListAPIView,
    LibraryItemDetailAPIView,
    LibraryItemListCreateAPIView,
    MyLibraryItemsAPIView,
    SearchLibraryItemsAPIView,
)

app_name = 'library'

urlpatterns = [
    path('categories/', LibraryCategoryListAPIView.as_view(), name='categories'),
    path('items/', LibraryItemListCreateAPIView.as_view(), name='items'),
    path('items/search/', SearchLibraryItemsAPIView.as_view(), name='item-search'),
    path('items/me/', MyLibraryItemsAPIView.as_view(), name='my-items'),
    path('items/<str:item_code>/', LibraryItemDetailAPIView.as_view(), name='item-detail'),
    path('items/<str:item_code>/download/', DownloadLibraryItemAPIView.as_view(), name='item-download'),
]
