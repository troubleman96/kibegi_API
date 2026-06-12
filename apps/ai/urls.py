from django.urls import path
from .views import AIChatView, AIConversationListView, AIConversationDetailView, AIUsageView

urlpatterns = [
    path('chat/', AIChatView.as_view(), name='ai_chat'),
    path('conversations/', AIConversationListView.as_view(), name='ai_conversations'),
    path('conversations/<uuid:conversation_id>/', AIConversationDetailView.as_view(), name='ai_conversation_detail'),
    path('usage/', AIUsageView.as_view(), name='ai_usage'),
]
