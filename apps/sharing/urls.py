from django.urls import path
from .views import (
    ShareFileAPIView, BulkShareAPIView, ShareRequestListAPIView,
    SharedWithMeAPIView, MySharesAPIView, AcceptShareAPIView,
    RejectShareAPIView, ShareDetailAPIView, DownloadSharedFileAPIView
)

app_name = 'sharing'

urlpatterns = [
    # Share a file
    path('', ShareFileAPIView.as_view(), name='share_file'),
    
    # Bulk share
    path('bulk/', BulkShareAPIView.as_view(), name='bulk_share'),
    
    # List views
    path('requests/', ShareRequestListAPIView.as_view(), name='share_requests'),
    path('shared-with-me/', SharedWithMeAPIView.as_view(), name='shared_with_me'),
    path('my-shares/', MySharesAPIView.as_view(), name='my_shares'),
    
    # Accept/reject
    path('<uuid:share_id>/accept/', AcceptShareAPIView.as_view(), name='accept_share'),
    path('<uuid:share_id>/reject/', RejectShareAPIView.as_view(), name='reject_share'),
    
    # Download shared file
    path('<uuid:share_id>/download/', DownloadSharedFileAPIView.as_view(), name='download_shared_file'),
    
    # Detail view
    path('<uuid:share_id>/', ShareDetailAPIView.as_view(), name='share_detail'),
]

