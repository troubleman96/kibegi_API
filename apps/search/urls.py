from django.urls import path

from .views import SearchAPIView, SearchHistoryAPIView, SearchSuggestionsAPIView

app_name = 'search'

urlpatterns = [
    path('', SearchAPIView.as_view(), name='search'),
    path('suggestions/', SearchSuggestionsAPIView.as_view(), name='search-suggestions'),
    path('history/', SearchHistoryAPIView.as_view(), name='search-history'),
]
