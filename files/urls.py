from django.urls import path
from .views import (
    AllFilesAPIView,
    MyUploadsAPIView,
    SharedWithMeAPIView,
    DeletedFilesAPIView,
    SingleFileDetailAPIView,
    PermanentDeleteFileAPIView,
    RestoreFileAPIView,
)

app_name = 'files'

urlpatterns = [
    path('all/', AllFilesAPIView.as_view(), name='all-files'),
    path('my-uploads/', MyUploadsAPIView.as_view(), name='my-uploads'),
    path('shared-with-me/', SharedWithMeAPIView.as_view(), name='shared-with-me'),
    path('deleted/', DeletedFilesAPIView.as_view(), name='deleted-files'),
    path('<str:file_code>/restore/', RestoreFileAPIView.as_view(), name='restore'),
    path('<str:file_code>/permanent-delete/', PermanentDeleteFileAPIView.as_view(), name='permanent-delete'),
    path('<str:file_code>/', SingleFileDetailAPIView.as_view(), name='file-detail'),
]
