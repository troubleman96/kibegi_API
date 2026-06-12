"""
URL configuration for kibegi_api project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.authentication.views import RegisterAPIView, LoginAPIView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # API v1 endpoints
    path('api/v1/', include('apps.core.urls')),           # health check
    path('api/v1/search/', include('apps.search.urls')),  # search app
    path('api/v1/auth/', include('apps.authentication.urls')),
    path('api/v1/classes/', include('apps.classes.urls')),
    path('api/v1/uploads/', include('apps.uploads.urls')),
    path('api/v1/sharing/', include('apps.sharing.urls')),
    path('api/v1/friends/', include('apps.friends.urls')),
    path('api/v1/notifications/', include('apps.notifications.urls')),
    path('api/v1/files/', include('apps.files.urls')),
    path('api/v1/storage/', include('apps.storage.urls')),
    path('api/v1/schedule/', include('apps.schedule.urls')),
    path('api/v1/public/schedule/', include('apps.schedule.public_urls')),
    path('api/v1/marketplace/', include('apps.marketplace.urls')),
    path('api/v1/library/', include('apps.library.urls')),
    path('api/v1/class-comms/', include('apps.classcomms.urls')),
    path('api/v1/public/class-comms/', include('apps.classcomms.public_urls')),
    path('api/v1/sms/', include('apps.sms.urls')),
    path('api/v1/assignments/', include('apps.assignments.urls')),
    path('api/v1/ai/', include('apps.ai.urls')),

    # Compatibility shortcuts (deprecated - use /api/v1/auth/ instead)
    path('register/', RegisterAPIView.as_view()),
    path('login/', LoginAPIView.as_view()),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
