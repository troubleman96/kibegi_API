from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.core.pagination import StandardResultsSetPagination
from apps.core.utils.responses import error_response, success_response

from .models import Channel, ChannelBroadcast, ChannelMember, ChannelWallet
from .serializers import (
    ChannelBroadcastSerializer,
    ChannelCreateSerializer,
    ChannelMemberSerializer,
    ChannelMemberUpsertSerializer,
    ChannelSerializer,
    ChannelWalletSerializer,
)
from .services import ChannelService


class ChannelAccessMixin:
    def get_object(self):
        return get_object_or_404(Channel, pk=self.kwargs.get('channel_id'))

    def ensure_member_access(self, request, channel):
        if channel.visibility == Channel.VISIBILITY_PUBLIC:
            return None
        if ChannelMember.objects.filter(channel=channel, user=request.user, is_active=True).exists():
            return None
        return error_response(message='You must join this channel first.', status_code=status.HTTP_403_FORBIDDEN)

    def ensure_manage_access(self, request, channel):
        if not ChannelService.user_can_manage(request.user, channel):
            return error_response(message='You do not have permission to manage this channel.', status_code=status.HTTP_403_FORBIDDEN)
        return None


@extend_schema(tags=['Channels'])
class ChannelListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self, request):
        q = (request.query_params.get('search') or request.query_params.get('q') or '').strip()
        base = Channel.objects.filter(is_active=True).select_related('created_by').prefetch_related('memberships')
        own_or_joined = base.filter(
            visibility=Channel.VISIBILITY_PUBLIC
        ) | base.filter(
            memberships__user=request.user,
            memberships__is_active=True,
        )
        if q:
            own_or_joined = own_or_joined.filter(name__icontains=q)
        return own_or_joined.distinct().order_by('name')

    def get(self, request):
        queryset = self.get_queryset(request)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        serializer = ChannelSerializer(page if page is not None else queryset, many=True, context={'request': request})
        if page is not None:
            payload = paginator.get_paginated_response(serializer.data)
            return success_response(message='Channels retrieved successfully', data=payload.data)
        return success_response(message='Channels retrieved successfully', data=serializer.data)

    def post(self, request):
        serializer = ChannelCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        channel = ChannelService.create_channel(
            creator=request.user,
            name=serializer.validated_data['name'],
            description=serializer.validated_data.get('description', ''),
            visibility=serializer.validated_data.get('visibility', Channel.VISIBILITY_PUBLIC),
        )
        out = ChannelSerializer(channel, context={'request': request})
        return success_response(message='Channel created successfully', data=out.data, status_code=status.HTTP_201_CREATED)


@extend_schema(tags=['Channels'])
class ChannelDetailAPIView(ChannelAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, channel_id):
        channel = self.get_object()
        denied = self.ensure_member_access(request, channel)
        if denied:
            return denied
        serializer = ChannelSerializer(channel, context={'request': request})
        return success_response(message='Channel retrieved successfully', data=serializer.data)

    def patch(self, request, channel_id):
        channel = self.get_object()
        denied = self.ensure_manage_access(request, channel)
        if denied:
            return denied
        serializer = ChannelCreateSerializer(channel, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(message='Channel updated successfully', data=ChannelSerializer(channel, context={'request': request}).data)


@extend_schema(tags=['Channels'])
class ChannelMemberListCreateAPIView(ChannelAccessMixin, APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self, channel):
        return channel.memberships.select_related('user', 'invited_by').filter(is_active=True).order_by('display_name')

    def get(self, request, channel_id):
        channel = self.get_object()
        denied = self.ensure_member_access(request, channel)
        if denied:
            return denied
        queryset = self.get_queryset(channel)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        serializer = ChannelMemberSerializer(page if page is not None else queryset, many=True, context={'request': request})
        if page is not None:
            payload = paginator.get_paginated_response(serializer.data)
            return success_response(message='Channel members retrieved successfully', data=payload.data)
        return success_response(message='Channel members retrieved successfully', data=serializer.data)

    def post(self, request, channel_id):
        channel = self.get_object()
        denied = self.ensure_manage_access(request, channel)
        if denied:
            return denied
        serializer = ChannelMemberUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            member = ChannelService.add_member(
                channel,
                identifier=serializer.validated_data['identifier'],
                actor=request.user,
                role=serializer.validated_data.get('role', ChannelMember.ROLE_MEMBER),
            )
        except (PermissionError, ValueError) as exc:
            return error_response(message=str(exc), status_code=status.HTTP_400_BAD_REQUEST)
        return success_response(message='Member added successfully', data=ChannelMemberSerializer(member, context={'request': request}).data, status_code=status.HTTP_201_CREATED)


@extend_schema(tags=['Channels'])
class ChannelMemberDetailAPIView(ChannelAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return get_object_or_404(ChannelMember, pk=self.kwargs.get('member_id'))

    def delete(self, request, member_id):
        member = self.get_object()
        denied = self.ensure_manage_access(request, member.channel)
        if denied:
            return denied
        if member.role == ChannelMember.ROLE_OWNER:
            return error_response(message='Channel owner cannot be removed.', status_code=status.HTTP_400_BAD_REQUEST)
        member.is_active = False
        member.left_at = timezone.now()
        member.save(update_fields=['is_active', 'left_at', 'updated_at'])
        return success_response(message='Member removed successfully')


@extend_schema(tags=['Channels'])
class ChannelJoinAPIView(ChannelAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, channel_id):
        channel = self.get_object()
        if channel.visibility == Channel.VISIBILITY_PRIVATE:
            return error_response(message='This channel is private. Use the invite link to join.', status_code=status.HTTP_403_FORBIDDEN)
        try:
            member = ChannelService.join_channel(channel, request.user)
        except (PermissionError, ValueError) as exc:
            return error_response(message=str(exc), status_code=status.HTTP_400_BAD_REQUEST)
        return success_response(message='Joined channel successfully', data=ChannelMemberSerializer(member, context={'request': request}).data, status_code=status.HTTP_201_CREATED)


@extend_schema(tags=['Channels'])
class ChannelWalletAPIView(ChannelAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, channel_id):
        channel = self.get_object()
        denied = self.ensure_member_access(request, channel)
        if denied:
            return denied
        wallet = ChannelService.get_wallet(channel)
        return success_response(message='Channel wallet retrieved successfully', data=ChannelWalletSerializer(wallet, context={'request': request}).data)

    def patch(self, request, channel_id):
        channel = self.get_object()
        denied = self.ensure_manage_access(request, channel)
        if denied:
            return denied
        wallet = ChannelService.get_wallet(channel)
        serializer = ChannelWalletSerializer(wallet, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(message='Channel wallet updated successfully', data=serializer.data)


@extend_schema(tags=['Channels'])
class ChannelBroadcastListCreateAPIView(ChannelAccessMixin, APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self, channel):
        return channel.broadcasts.select_related('sender').prefetch_related('deliveries').order_by('-created_at')

    def get(self, request, channel_id):
        channel = self.get_object()
        denied = self.ensure_member_access(request, channel)
        if denied:
            return denied
        queryset = self.get_queryset(channel)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        serializer = ChannelBroadcastSerializer(page if page is not None else queryset, many=True, context={'request': request})
        if page is not None:
            payload = paginator.get_paginated_response(serializer.data)
            return success_response(message='Channel broadcasts retrieved successfully', data=payload.data)
        return success_response(message='Channel broadcasts retrieved successfully', data=serializer.data)

    def post(self, request, channel_id):
        channel = self.get_object()
        denied = self.ensure_manage_access(request, channel)
        if denied:
            return denied
        serializer = ChannelBroadcastSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        broadcast = serializer.save(channel=channel, sender=request.user)
        ChannelService.dispatch_broadcast(broadcast)
        return success_response(message='Channel broadcast sent successfully', data=ChannelBroadcastSerializer(broadcast, context={'request': request}).data, status_code=status.HTTP_201_CREATED)


@extend_schema(tags=['Channels'])
class ChannelBroadcastDetailAPIView(ChannelAccessMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return get_object_or_404(ChannelBroadcast, pk=self.kwargs.get('broadcast_id'))

    def get(self, request, broadcast_id):
        broadcast = self.get_object()
        denied = self.ensure_member_access(request, broadcast.channel)
        if denied:
            return denied
        return success_response(message='Channel broadcast retrieved successfully', data=ChannelBroadcastSerializer(broadcast, context={'request': request}).data)


@extend_schema(tags=['Channels'])
class PublicChannelInfoAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, invite_token):
        channel = get_object_or_404(Channel, invite_token=invite_token, is_active=True)
        serializer = ChannelSerializer(channel, context={'request': request})
        data = serializer.data
        data['join_hint'] = 'Create a Kibegi account, then join this channel to receive campaign messages.'
        data['member_count'] = channel.memberships.filter(is_active=True).count()
        return success_response(message='Channel info retrieved successfully', data=data)


@extend_schema(tags=['Channels'])
class PublicChannelJoinAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, invite_token):
        channel = get_object_or_404(Channel, invite_token=invite_token, is_active=True)
        try:
            member = ChannelService.join_channel(channel, request.user)
        except (PermissionError, ValueError) as exc:
            return error_response(message=str(exc), status_code=status.HTTP_400_BAD_REQUEST)
        return success_response(message='Channel joined successfully', data=ChannelMemberSerializer(member, context={'request': request}).data, status_code=status.HTTP_201_CREATED)
