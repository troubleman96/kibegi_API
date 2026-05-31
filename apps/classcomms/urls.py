from django.urls import path

from .views import (
    ClassBroadcastDetailAPIView,
    ClassBroadcastListCreateAPIView,
    ClassCommsProfileAPIView,
    ClassCommsWalletAPIView,
    ClassContactDetailAPIView,
    ClassContactListCreateAPIView,
    ClassRepresentativeAPIView,
)

urlpatterns = [
    path('classes/<uuid:class_id>/profile/', ClassCommsProfileAPIView.as_view(), name='classcomms_profile'),
    path('classes/<uuid:class_id>/wallet/', ClassCommsWalletAPIView.as_view(), name='classcomms_wallet'),
    path('classes/<uuid:class_id>/contacts/', ClassContactListCreateAPIView.as_view(), name='classcomms_contacts'),
    path('contacts/<uuid:pk>/', ClassContactDetailAPIView.as_view(), name='classcomms_contact_detail'),
    path('classes/<uuid:class_id>/broadcasts/', ClassBroadcastListCreateAPIView.as_view(), name='classcomms_broadcasts'),
    path('broadcasts/<uuid:pk>/', ClassBroadcastDetailAPIView.as_view(), name='classcomms_broadcast_detail'),
    path('classes/<uuid:class_id>/representatives/', ClassRepresentativeAPIView.as_view(), name='classcomms_representatives'),
]
