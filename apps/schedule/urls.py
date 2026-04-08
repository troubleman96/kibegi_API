from django.urls import path

from .views import (
    ScheduleCalendarDetailAPIView,
    ScheduleCalendarEventsAPIView,
    ScheduleCalendarListAPIView,
    ScheduleCalendarQRAPIView,
    ScheduleCalendarShareAPIView,
    ScheduleEventDetailAPIView,
)


urlpatterns = [
    path("calendars/", ScheduleCalendarListAPIView.as_view(), name="schedule_calendar_list"),
    path("calendars/<int:pk>/", ScheduleCalendarDetailAPIView.as_view(), name="schedule_calendar_detail"),
    path("calendars/<int:pk>/events/", ScheduleCalendarEventsAPIView.as_view(), name="schedule_calendar_events"),
    path("events/<int:pk>/", ScheduleEventDetailAPIView.as_view(), name="schedule_event_detail"),
    path("calendars/<int:pk>/share/", ScheduleCalendarShareAPIView.as_view(), name="schedule_calendar_share"),
    path("calendars/<int:pk>/qr/", ScheduleCalendarQRAPIView.as_view(), name="schedule_calendar_qr"),
]
