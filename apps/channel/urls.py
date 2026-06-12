from django.urls import path

from .views import (
    ChannelBroadcastDetailAPIView,
    ChannelBroadcastListCreateAPIView,
    ChannelDetailAPIView,
    ChannelJoinAPIView,
    ChannelListCreateAPIView,
    ChannelMemberDetailAPIView,
    ChannelMemberListCreateAPIView,
    ChannelWalletAPIView,
)

urlpatterns = [
    path('channels/', ChannelListCreateAPIView.as_view(), name='channel_list_create'),
    path('channels/<uuid:channel_id>/', ChannelDetailAPIView.as_view(), name='channel_detail'),
    path('channels/<uuid:channel_id>/wallet/', ChannelWalletAPIView.as_view(), name='channel_wallet'),
    path('channels/<uuid:channel_id>/members/', ChannelMemberListCreateAPIView.as_view(), name='channel_members'),
    path('members/<uuid:member_id>/', ChannelMemberDetailAPIView.as_view(), name='channel_member_detail'),
    path('channels/<uuid:channel_id>/join/', ChannelJoinAPIView.as_view(), name='channel_join'),
    path('channels/<uuid:channel_id>/broadcasts/', ChannelBroadcastListCreateAPIView.as_view(), name='channel_broadcasts'),
    path('broadcasts/<uuid:broadcast_id>/', ChannelBroadcastDetailAPIView.as_view(), name='channel_broadcast_detail'),
]

