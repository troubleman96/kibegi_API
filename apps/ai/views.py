from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.classes.models import Class, Membership
from apps.core.utils.responses import success_response, error_response

from .models import AIConversation, AIMessage, AIUsage, AIProcessingJob, UserAIProfile
from .chat import chat, resolve_api_key


class AIChatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        class_id = request.data.get('class_id') or None
        message = (request.data.get('message') or '').strip()
        conversation_id = request.data.get('conversation_id')

        if not message:
            return error_response("message is required", status_code=status.HTTP_400_BAD_REQUEST)
        if len(message) > 2000:
            return error_response("Message too long (max 2000 characters)", status_code=status.HTTP_400_BAD_REQUEST)

        class_obj = None
        if class_id:
            class_obj = get_object_or_404(Class, id=class_id)
            if not Membership.objects.filter(user=user, class_obj=class_obj).exists():
                return error_response(
                    "You are not a member of this class",
                    status_code=status.HTTP_403_FORBIDDEN,
                )

        api_key, _ = resolve_api_key(user)
        if not api_key:
            return error_response(
                "No AI API key configured. Add your Ngamia API key in Settings to use Kibegi AI.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        usage, _ = AIUsage.objects.get_or_create(user=user)
        if not usage.can_use_ai():
            return error_response(
                f"Daily AI limit reached ({usage.daily_limit:,} tokens). Resets at midnight.",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        conversation = None
        if conversation_id:
            filters = {"id": conversation_id, "user": user}
            if class_obj:
                filters["class_obj"] = class_obj
            else:
                filters["class_obj__isnull"] = True
            try:
                conversation = AIConversation.objects.get(**filters)
            except AIConversation.DoesNotExist:
                pass

        if not conversation:
            title = message[:80] + ('…' if len(message) > 80 else '')
            conversation = AIConversation.objects.create(
                user=user, class_obj=class_obj, title=title
            )

        AIMessage.objects.create(
            conversation=conversation,
            role=AIMessage.ROLE_USER,
            content=message,
        )

        result = chat(message, class_obj, conversation, user)

        AIMessage.objects.create(
            conversation=conversation,
            role=AIMessage.ROLE_ASSISTANT,
            content=result['response'],
            sources=result['sources'],
            tokens_used=result['tokens_used'],
        )

        if result['tokens_used'] > 0:
            usage.record_usage(result['tokens_used'])

        conversation.save(update_fields=['updated_at'])

        return success_response(
            message="AI response generated",
            data={
                "conversation_id": str(conversation.id),
                "response": result['response'],
                "sources": result['sources'],
                "tokens_used": result['tokens_used'],
                "practice_mode": result.get('practice_mode', False),
                "usage": {
                    "tokens_today": usage.tokens_used_today,
                    "daily_limit": usage.daily_limit,
                },
            },
        )


class AIConversationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        class_id = request.query_params.get('class_id')
        qs = AIConversation.objects.filter(user=request.user)
        if class_id:
            qs = qs.filter(class_obj_id=class_id)
        data = [
            {
                "id": str(c.id),
                "title": c.title or "Untitled conversation",
                "class_name": c.class_obj.name if c.class_obj else "General",
                "class_id": str(c.class_obj.id) if c.class_obj else None,
                "updated_at": c.updated_at.isoformat(),
                "message_count": c.messages.count(),
            }
            for c in qs[:20]
        ]
        return success_response(message="Conversations retrieved", data=data)


class AIConversationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        conv = get_object_or_404(AIConversation, id=conversation_id, user=request.user)
        data = {
            "id": str(conv.id),
            "title": conv.title,
            "class_name": conv.class_obj.name if conv.class_obj else "General",
            "class_id": str(conv.class_obj.id) if conv.class_obj else None,
            "messages": [
                {
                    "id": str(m.id),
                    "role": m.role,
                    "content": m.content,
                    "sources": m.sources,
                    "created_at": m.created_at.isoformat(),
                }
                for m in conv.messages.order_by('created_at')
            ],
        }
        return success_response(message="Conversation retrieved", data=data)

    def delete(self, request, conversation_id):
        conv = get_object_or_404(AIConversation, id=conversation_id, user=request.user)
        conv.delete()
        return success_response(message="Conversation deleted")


class AISettingsView(APIView):
    """Get / save / clear the user's own Ngamia API key and preferred model."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile, _ = UserAIProfile.objects.get_or_create(user=request.user)
        return success_response(
            message="AI settings retrieved",
            data={
                "has_key": profile.has_key,
                "masked_key": profile.masked_key,
                "chat_model": profile.chat_model or settings.AI_CHAT_MODEL,
            },
        )

    def post(self, request):
        api_key = (request.data.get('api_key') or '').strip()
        chat_model = (request.data.get('chat_model') or '').strip() or settings.AI_CHAT_MODEL

        if not api_key:
            return error_response("api_key is required", status_code=status.HTTP_400_BAD_REQUEST)
        if len(api_key) > 300:
            return error_response("API key is too long", status_code=status.HTTP_400_BAD_REQUEST)

        profile, _ = UserAIProfile.objects.get_or_create(user=request.user)
        profile.api_key = api_key
        profile.chat_model = chat_model
        profile.save(update_fields=['api_key', 'chat_model', 'updated_at'])

        return success_response(
            message="AI settings saved",
            data={
                "has_key": True,
                "masked_key": profile.masked_key,
                "chat_model": profile.chat_model,
            },
        )

    def delete(self, request):
        UserAIProfile.objects.filter(user=request.user).delete()
        return success_response(message="AI settings cleared")


class AIUsageView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        usage, _ = AIUsage.objects.get_or_create(user=request.user)
        usage.reset_if_needed()
        remaining = max(0, usage.daily_limit - usage.tokens_used_today)
        return success_response(
            message="AI usage retrieved",
            data={
                "tokens_today": usage.tokens_used_today,
                "tokens_total": usage.tokens_used_total,
                "daily_limit": usage.daily_limit,
                "remaining_today": remaining,
                "percentage_used": round((usage.tokens_used_today / usage.daily_limit) * 100, 1),
            },
        )


class AIProcessingStatusView(APIView):
    """Return processing status for an uploaded file."""
    permission_classes = [IsAuthenticated]

    def get(self, request, upload_id):
        from apps.uploads.models import Upload
        upload = get_object_or_404(Upload, id=upload_id, is_deleted=False)

        # Only class members can check
        if not Membership.objects.filter(
            user=request.user, class_obj=upload.class_obj
        ).exists():
            return error_response("Not a member of this class", status_code=status.HTTP_403_FORBIDDEN)

        try:
            job = upload.ai_job
            return success_response(
                message="Processing status",
                data={
                    "upload_id": str(upload.id),
                    "file_name": upload.file_name,
                    "status": job.status,
                    "chunks_created": job.chunks_created,
                    "error_message": job.error_message or None,
                    "updated_at": job.updated_at.isoformat(),
                },
            )
        except AIProcessingJob.DoesNotExist:
            return success_response(
                message="Processing status",
                data={
                    "upload_id": str(upload.id),
                    "file_name": upload.file_name,
                    "status": "not_started",
                    "chunks_created": 0,
                    "error_message": None,
                    "updated_at": None,
                },
            )

    def post(self, request, upload_id):
        """Manually trigger (re)processing of a file."""
        from apps.uploads.models import Upload
        from .processing import process_upload_async, should_process

        upload = get_object_or_404(Upload, id=upload_id, is_deleted=False)
        if not Membership.objects.filter(
            user=request.user, class_obj=upload.class_obj
        ).exists():
            return error_response("Not a member of this class", status_code=status.HTTP_403_FORBIDDEN)

        if not should_process(upload):
            return error_response(
                "This file type is not supported for AI processing",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Reset job so it re-runs
        job, _ = AIProcessingJob.objects.get_or_create(upload=upload)
        job.status = AIProcessingJob.STATUS_PENDING
        job.error_message = ''
        job.save(update_fields=['status', 'error_message'])

        process_upload_async(str(upload.id))

        return success_response(
            message="Processing started",
            data={"upload_id": str(upload.id), "status": "pending"},
        )
