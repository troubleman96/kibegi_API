"""
URL configuration for core app.

Contains routes for cross-cutting functionality like global search.
"""

from django.urls import path
from .views import GlobalSearchAPIView

app_name = 'core'

urlpatterns = [
    # Global search endpoint
    path('search/', GlobalSearchAPIView.as_view(), name='global-search'),
]

