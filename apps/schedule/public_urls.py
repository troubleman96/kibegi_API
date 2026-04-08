from django.urls import path

from .views import (
    PublicScheduleCodeInfoAPIView,
    PublicScheduleDownloadAPIView,
    PublicScheduleInfoAPIView,
    PublicScheduleSubscribeAPIView,
)


urlpatterns = [
    path("<str:token>/subscribe/", PublicScheduleSubscribeAPIView.as_view(), name="schedule_public_subscribe"),
    path("<str:token>/download/", PublicScheduleDownloadAPIView.as_view(), name="schedule_public_download"),
    path("<str:token>/info/", PublicScheduleInfoAPIView.as_view(), name="schedule_public_info"),
    path("code/<str:code>/info/", PublicScheduleCodeInfoAPIView.as_view(), name="schedule_public_code_info"),
]

