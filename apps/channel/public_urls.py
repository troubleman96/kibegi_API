from django.urls import path

from .views import PublicChannelInfoAPIView, PublicChannelJoinAPIView

urlpatterns = [
    path('<str:invite_token>/info/', PublicChannelInfoAPIView.as_view(), name='channel_public_info'),
    path('<str:invite_token>/join/', PublicChannelJoinAPIView.as_view(), name='channel_public_join'),
]

