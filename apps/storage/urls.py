"""
Storage App URL Configuration

This module defines URL patterns for the storage app.
All endpoints are prefixed with /api/v1/storage/
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserStorageViewSet

# Create a router and register our viewsets
router = DefaultRouter()
router.register(r'', UserStorageViewSet, basename='storage')

# URL patterns
urlpatterns = [
    path('', include(router.urls)),
]


