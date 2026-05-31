from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.classes.models import Class, Membership
from apps.core.pagination import StandardResultsSetPagination
from apps.core.utils.responses import error_response, success_response

from .models import ClassBroadcast, ClassCommsProfile, ClassCommsWallet, ClassContact
from .serializers import (
    ClassBroadcastSerializer,
    ClassContactSerializer,
    ClassContactUpsertSerializer,
    ClassCommsProfileSerializer,
    ClassCommsWalletSerializer,
    ClassRepresentativeSerializer,
)
from .services import ClassCommsService


class ClassCommsPermissionMixin:
    """Shared access checks for class communications endpoints."""

    def get_class_object(self):
        return get_object_or_404(Class, pk=self.kwargs.get('class_id'))

    def ensure_manager_access(self, request, class_obj):
        if not ClassCommsService.user_can_manage_class_comms(request.user, class_obj):
            return error_response(
                message="You don't have permission to manage class communications for this class.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return None


@extend_schema(tags=['Class Communications'])
class ClassCommsProfileAPIView(ClassCommsPermissionMixin, APIView):
    """Read and update the public registration settings for a class."""

    permission_classes = [IsAuthenticated]

    def get(self, request, class_id):
        class_obj = self.get_class_object()
        denied = self.ensure_manager_access(request, class_obj)
        if denied:
            return denied

        profile = ClassCommsService.get_profile_for_class(class_obj)
        serializer = ClassCommsProfileSerializer(profile, context={'request': request})
        return success_response(message='Class communications profile retrieved successfully', data=serializer.data)

    def patch(self, request, class_id):
        class_obj = self.get_class_object()
        denied = self.ensure_manager_access(request, class_obj)
        if denied:
            return denied

        profile = ClassCommsService.get_profile_for_class(class_obj)
        serializer = ClassCommsProfileSerializer(profile, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(message='Class communications profile updated successfully', data=serializer.data)


@extend_schema(tags=['Class Communications'])
class ClassCommsWalletAPIView(ClassCommsPermissionMixin, APIView):
    """Inspect and update the SMS credit wallet for a class."""

    permission_classes = [IsAuthenticated]

    def get(self, request, class_id):
        class_obj = self.get_class_object()
        denied = self.ensure_manager_access(request, class_obj)
        if denied:
            return denied

        wallet = ClassCommsService.get_wallet_for_class(class_obj)
        serializer = ClassCommsWalletSerializer(wallet, context={'request': request})
        return success_response(message='Class wallet retrieved successfully', data=serializer.data)

    def patch(self, request, class_id):
        class_obj = self.get_class_object()
        denied = self.ensure_manager_access(request, class_obj)
        if denied:
            return denied

        wallet = ClassCommsService.get_wallet_for_class(class_obj)
        serializer = ClassCommsWalletSerializer(wallet, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(message='Class wallet updated successfully', data=serializer.data)


@extend_schema(tags=['Class Communications'])
class ClassContactListCreateAPIView(ClassCommsPermissionMixin, APIView):
    """List and create class contacts for SMS broadcasts."""

    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self, class_obj):
        return class_obj.comms_contacts.select_related('created_by', 'registered_by').order_by('full_name')

    def get(self, request, class_id):
        class_obj = self.get_class_object()
        denied = self.ensure_manager_access(request, class_obj)
        if denied:
            return denied

        queryset = self.get_queryset(class_obj)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        serializer = ClassContactSerializer(page if page is not None else queryset, many=True, context={'request': request})
        if page is not None:
            payload = paginator.get_paginated_response(serializer.data)
            return success_response(message='Class contacts retrieved successfully', data=payload.data)
        return success_response(message='Class contacts retrieved successfully', data=serializer.data)

    def post(self, request, class_id):
        class_obj = self.get_class_object()
        denied = self.ensure_manager_access(request, class_obj)
        if denied:
            return denied

        serializer = ClassContactUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        contact, created = ClassCommsService.upsert_contact(
            class_obj,
            full_name=serializer.validated_data['full_name'],
            phone_number=serializer.validated_data['phone_number'],
            consent_granted=serializer.validated_data.get('consent_granted', True),
            consent_source=ClassContact.SOURCE_MANUAL,
            notes=serializer.validated_data.get('notes', ''),
            registered_by=request.user,
            created_by=request.user,
        )
        contact_serializer = ClassContactSerializer(contact, context={'request': request})
        return success_response(
            message='Class contact created successfully' if created else 'Class contact updated successfully',
            data=contact_serializer.data,
            status_code=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


@extend_schema(tags=['Class Communications'])
class ClassContactDetailAPIView(ClassCommsPermissionMixin, APIView):
    """Retrieve, update, or delete a single class contact."""

    permission_classes = [IsAuthenticated]

    def get_object(self):
        return get_object_or_404(ClassContact, pk=self.kwargs.get('pk'))

    def get(self, request, pk):
        contact = self.get_object()
        class_obj = contact.class_obj
        denied = self.ensure_manager_access(request, class_obj)
        if denied:
            return denied
        serializer = ClassContactSerializer(contact, context={'request': request})
        return success_response(message='Class contact retrieved successfully', data=serializer.data)

    def patch(self, request, pk):
        contact = self.get_object()
        class_obj = contact.class_obj
        denied = self.ensure_manager_access(request, class_obj)
        if denied:
            return denied
        serializer = ClassContactSerializer(contact, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(message='Class contact updated successfully', data=serializer.data)

    def delete(self, request, pk):
        contact = self.get_object()
        class_obj = contact.class_obj
        denied = self.ensure_manager_access(request, class_obj)
        if denied:
            return denied
        contact.delete()
        return success_response(message='Class contact deleted successfully')


@extend_schema(tags=['Class Communications'])
class ClassRepresentativeAPIView(ClassCommsPermissionMixin, APIView):
    """Promote or demote class members that manage communications."""

    permission_classes = [IsAuthenticated]

    def post(self, request, class_id):
        class_obj = self.get_class_object()
        denied = self.ensure_manager_access(request, class_obj)
        if denied:
            return denied

        serializer = ClassRepresentativeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member = get_object_or_404(Membership, class_obj=class_obj, user_id=serializer.validated_data['user_id'])
        member.role = serializer.validated_data['role']
        member.save(update_fields=['role'])
        return success_response(
            message='Class representative role updated successfully',
            data={
                'membership_id': str(member.id),
                'user_id': str(member.user_id),
                'role': member.role,
            },
        )


@extend_schema(tags=['Class Communications'])
class ClassBroadcastListCreateAPIView(ClassCommsPermissionMixin, APIView):
    """List broadcasts for a class and send new SMS announcements."""

    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self, class_obj):
        return class_obj.comms_broadcasts.select_related('sender').prefetch_related('deliveries').order_by('-created_at')

    def get(self, request, class_id):
        class_obj = self.get_class_object()
        denied = self.ensure_manager_access(request, class_obj)
        if denied:
            return denied

        queryset = self.get_queryset(class_obj)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        serializer = ClassBroadcastSerializer(page if page is not None else queryset, many=True, context={'request': request})
        if page is not None:
            payload = paginator.get_paginated_response(serializer.data)
            return success_response(message='Class broadcasts retrieved successfully', data=payload.data)
        return success_response(message='Class broadcasts retrieved successfully', data=serializer.data)

    def post(self, request, class_id):
        class_obj = self.get_class_object()
        denied = self.ensure_manager_access(request, class_obj)
        if denied:
            return denied

        serializer = ClassBroadcastSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        broadcast = serializer.save(class_obj=class_obj, sender=request.user)
        ClassCommsService.dispatch_broadcast(broadcast)
        refreshed = ClassBroadcastSerializer(broadcast, context={'request': request})
        return success_response(
            message='Class broadcast sent successfully',
            data=refreshed.data,
            status_code=status.HTTP_201_CREATED,
        )


@extend_schema(tags=['Class Communications'])
class ClassBroadcastDetailAPIView(ClassCommsPermissionMixin, APIView):
    """Inspect a single broadcast and its delivery summary."""

    permission_classes = [IsAuthenticated]

    def get_object(self):
        return get_object_or_404(ClassBroadcast, pk=self.kwargs.get('pk'))

    def get(self, request, pk):
        broadcast = self.get_object()
        class_obj = broadcast.class_obj
        denied = self.ensure_manager_access(request, class_obj)
        if denied:
            return denied
        serializer = ClassBroadcastSerializer(broadcast, context={'request': request})
        return success_response(message='Class broadcast retrieved successfully', data=serializer.data)


@extend_schema(tags=['Class Communications'])
class PublicRegistrationInfoAPIView(APIView):
    """Expose public class registration metadata for the frontend."""

    permission_classes = [AllowAny]

    def get(self, request, public_token):
        profile = get_object_or_404(ClassCommsProfile, public_token=public_token)
        if not profile.public_registration_enabled:
            return error_response(message='Public registration is disabled for this class.', status_code=status.HTTP_403_FORBIDDEN)

        class_obj = profile.class_obj
        wallet = ClassCommsService.get_wallet_for_class(class_obj)
        data = {
            'class_id': str(class_obj.id),
            'class_name': class_obj.name,
            'class_code': class_obj.class_code,
            'description': class_obj.description,
            'registration_hint': profile.registration_hint,
            'public_registration_enabled': profile.public_registration_enabled,
            'default_sender_name': profile.default_sender_name,
            'credits_remaining': wallet.balance_credits,
            'contacts_registered': class_obj.comms_contacts.filter(is_active=True).count(),
            'registration_urls': ClassCommsService.build_registration_urls(request, class_obj),
        }
        return success_response(message='Public registration info retrieved successfully', data=data)


@extend_schema(tags=['Class Communications'])
class PublicRegistrationAPIView(APIView):
    """Accept name and phone number from a public registration link."""

    permission_classes = [AllowAny]

    def post(self, request, public_token):
        profile = get_object_or_404(ClassCommsProfile, public_token=public_token)
        if not profile.public_registration_enabled:
            return error_response(message='Public registration is disabled for this class.', status_code=status.HTTP_403_FORBIDDEN)

        serializer = ClassContactUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        contact, created = ClassCommsService.upsert_contact(
            profile.class_obj,
            full_name=serializer.validated_data['full_name'],
            phone_number=serializer.validated_data['phone_number'],
            consent_granted=serializer.validated_data.get('consent_granted', True),
            consent_source=ClassContact.SOURCE_PUBLIC,
            notes=serializer.validated_data.get('notes', ''),
            registered_by=None,
            created_by=None,
        )
        response_serializer = ClassContactSerializer(contact, context={'request': request})
        return success_response(
            message='Contact registered successfully' if created else 'Contact updated successfully',
            data=response_serializer.data,
            status_code=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
