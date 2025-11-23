from django.urls import path
from .views import (
    UploadListCreateAPIView,
    UploadDetailAPIView,
    TrashAPIView,
    RestoreUploadAPIView,
    PermanentDeleteAPIView,
    SearchUploadsAPIView,
    RecentFilesAPIView,
    DownloadFileAPIView,
)

app_name = 'uploads'

urlpatterns = [
    path('', UploadListCreateAPIView.as_view(), name='list-create'),
    path('search/', SearchUploadsAPIView.as_view(), name='search'),
    path('trash/', TrashAPIView.as_view(), name='trash'),
    path('recent/', RecentFilesAPIView.as_view(), name='recent'),
    path('<str:file_code>/download/', DownloadFileAPIView.as_view(), name='download'),
    path('<str:file_code>/', UploadDetailAPIView.as_view(), name='detail'),
    path('<uuid:pk>/restore/', RestoreUploadAPIView.as_view(), name='restore'),
    path('<uuid:pk>/permanent-delete/', PermanentDeleteAPIView.as_view(), name='permanent-delete'),
]
