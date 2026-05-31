from django.urls import path

from .views import PublicRegistrationInfoAPIView, PublicRegistrationAPIView

urlpatterns = [
    path('<str:public_token>/info/', PublicRegistrationInfoAPIView.as_view(), name='classcomms_public_info'),
    path('<str:public_token>/register/', PublicRegistrationAPIView.as_view(), name='classcomms_public_register'),
]
