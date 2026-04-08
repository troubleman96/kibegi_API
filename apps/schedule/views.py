from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from apps.core.utils.responses import success_response, error_response

from .models import ScheduleCalendar, ScheduleEvent
from .serializers import (
    PublicScheduleInfoSerializer,
    ScheduleCalendarDetailSerializer,
    ScheduleCalendarSerializer,
    ScheduleEventSerializer,
    ScheduleShareSerializer,
)
from .services import ScheduleService


class ScheduleCalendarListAPIView(generics.ListAPIView):
    """List the authenticated user's default schedule calendars."""

    permission_classes = [IsAuthenticated]
    serializer_class = ScheduleCalendarSerializer
    pagination_class = None

    def get_queryset(self):
        return (
            ScheduleService.get_user_calendars(self.request.user)
            .annotate(event_count=Count("events"))
        )

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return success_response(
            message="Schedule calendars retrieved successfully",
            data=serializer.data,
        )


class ScheduleCalendarDetailAPIView(generics.RetrieveUpdateAPIView):
    """Retrieve or update a single authenticated user's schedule calendar."""

    permission_classes = [IsAuthenticated]
    serializer_class = ScheduleCalendarDetailSerializer

    def get_queryset(self):
        return (
            ScheduleCalendar.objects.filter(owner=self.request.user)
            .annotate(event_count=Count("events"))
            .prefetch_related("events")
        )

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return success_response(
            message="Schedule calendar retrieved successfully",
            data=serializer.data,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(
            message="Schedule calendar updated successfully",
            data=serializer.data,
        )


class ScheduleCalendarEventsAPIView(generics.ListCreateAPIView):
    """List or create events for one authenticated schedule calendar."""

    permission_classes = [IsAuthenticated]
    serializer_class = ScheduleEventSerializer
    pagination_class = None

    def get_calendar(self):
        ScheduleService.ensure_default_calendars(self.request.user)
        return get_object_or_404(ScheduleCalendar, pk=self.kwargs["pk"], owner=self.request.user)

    def get_queryset(self):
        return self.get_calendar().events.all().order_by("start_at", "created_at")

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return success_response(
            message="Schedule events retrieved successfully",
            data=serializer.data,
        )

    def create(self, request, *args, **kwargs):
        calendar = self.get_calendar()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(calendar=calendar)
        return success_response(
            message="Schedule event created successfully",
            data=serializer.data,
            status_code=status.HTTP_201_CREATED,
        )


class ScheduleEventDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete one authenticated user's schedule event."""

    permission_classes = [IsAuthenticated]
    serializer_class = ScheduleEventSerializer

    def get_queryset(self):
        ScheduleService.ensure_default_calendars(self.request.user)
        return ScheduleEvent.objects.filter(calendar__owner=self.request.user).select_related("calendar")

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return success_response(
            message="Schedule event retrieved successfully",
            data=serializer.data,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(
            message="Schedule event updated successfully",
            data=serializer.data,
        )

    def destroy(self, request, *args, **kwargs):
        event = self.get_object()
        event.delete()
        return success_response(message="Schedule event deleted successfully", status_code=status.HTTP_200_OK)


class ScheduleCalendarShareAPIView(APIView):
    """Return tokenized sync/share links for one authenticated user's calendar."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        ScheduleService.ensure_default_calendars(request.user)
        try:
            calendar = ScheduleCalendar.objects.get(pk=pk, owner=request.user)
        except ScheduleCalendar.DoesNotExist:
            return error_response("Schedule calendar not found", status_code=status.HTTP_404_NOT_FOUND)

        serializer = ScheduleShareSerializer(ScheduleService.build_share_payload(request, calendar))
        return success_response(
            message="Schedule share information retrieved successfully",
            data=serializer.data,
        )


class ScheduleCalendarQRAPIView(APIView):
    """Return a PNG QR code that points at the public schedule info endpoint."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        ScheduleService.ensure_default_calendars(request.user)
        try:
            calendar = ScheduleCalendar.objects.get(pk=pk, owner=request.user)
        except ScheduleCalendar.DoesNotExist:
            return error_response("Schedule calendar not found", status_code=status.HTTP_404_NOT_FOUND)

        share_payload = ScheduleService.build_share_payload(request, calendar)
        qr_target = share_payload["frontend_subscription_url"] or share_payload["subscription_page_url"]
        png_bytes = ScheduleService.generate_qr_png(qr_target)
        return HttpResponse(png_bytes, content_type="image/png")


class PublicScheduleBaseAPIView(APIView):
    """Shared helpers for public token/code schedule endpoints."""

    permission_classes = [AllowAny]

    def get_calendar(self, token=None, code=None):
        queryset = ScheduleCalendar.objects.filter(is_public_sync=True)
        if token:
            return queryset.filter(share_token=token).first()
        if code:
            return queryset.filter(calendar_code=code.upper()).first()
        return None

    def build_public_info(self, request, calendar):
        share_payload = ScheduleService.build_share_payload(request, calendar)
        return {
            "name": calendar.name,
            "calendar_type": calendar.calendar_type,
            "description": calendar.description,
            "calendar_code": calendar.calendar_code,
            "event_count": calendar.events.count(),
            "subscribe_url": share_payload["subscribe_url"],
            "download_url": share_payload["download_url"],
            "webcal_url": share_payload["webcal_url"],
            "subscription_page_url": share_payload["subscription_page_url"],
            "frontend_subscription_url": share_payload["frontend_subscription_url"],
        }


class PublicScheduleInfoAPIView(PublicScheduleBaseAPIView):
    """Return public info for a tokenized shared calendar."""

    def get(self, request, token):
        calendar = self.get_calendar(token=token)
        if not calendar:
            return error_response("Schedule calendar not found", status_code=status.HTTP_404_NOT_FOUND)

        ScheduleService.record_public_access(calendar, request, "info")
        serializer = PublicScheduleInfoSerializer(self.build_public_info(request, calendar))
        return success_response(
            message="Public schedule information retrieved successfully",
            data=serializer.data,
        )


class PublicScheduleCodeInfoAPIView(PublicScheduleBaseAPIView):
    """Return public info for a short-code shared calendar."""

    def get(self, request, code):
        calendar = self.get_calendar(code=code)
        if not calendar:
            return error_response("Schedule calendar not found", status_code=status.HTTP_404_NOT_FOUND)

        ScheduleService.record_public_access(calendar, request, "code-info")
        serializer = PublicScheduleInfoSerializer(self.build_public_info(request, calendar))
        return success_response(
            message="Public schedule information retrieved successfully",
            data=serializer.data,
        )


class PublicScheduleSubscribeAPIView(PublicScheduleBaseAPIView):
    """Return a sync-friendly ICS feed for subscribed calendar clients."""

    def get(self, request, token):
        calendar = self.get_calendar(token=token)
        if not calendar:
            return error_response("Schedule calendar not found", status_code=status.HTTP_404_NOT_FOUND)

        ScheduleService.record_public_access(calendar, request, "subscribe")
        ics_content = ScheduleService.generate_ics(calendar, calendar.events.all())
        response = HttpResponse(ics_content, content_type="text/calendar; charset=utf-8")
        response["Content-Disposition"] = f'inline; filename="{calendar.calendar_type}-{calendar.calendar_code}.ics"'
        return response


class PublicScheduleDownloadAPIView(PublicScheduleBaseAPIView):
    """Return an attachment download for the public schedule ICS file."""

    def get(self, request, token):
        calendar = self.get_calendar(token=token)
        if not calendar:
            return error_response("Schedule calendar not found", status_code=status.HTTP_404_NOT_FOUND)

        ScheduleService.record_public_access(calendar, request, "download")
        ics_content = ScheduleService.generate_ics(calendar, calendar.events.all())
        response = HttpResponse(ics_content, content_type="text/calendar; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{calendar.calendar_type}-{calendar.calendar_code}.ics"'
        return response
