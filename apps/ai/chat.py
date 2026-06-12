import logging
from openai import OpenAI
from django.conf import settings

logger = logging.getLogger(__name__)


def get_client() -> OpenAI:
    return OpenAI(
        base_url=getattr(settings, 'OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1'),
        api_key=settings.OPENROUTER_API_KEY,
        default_headers={
            "HTTP-Referer": "https://kibegi.com",
            "X-Title": "Kibegi AI",
        },
    )


def build_class_context(class_obj) -> tuple[str, list[str]]:
    """Return a text summary of the class and a list of file names."""
    from apps.uploads.models import Upload

    uploads = list(
        Upload.objects.filter(class_obj=class_obj, is_deleted=False)
        .select_related('uploader')
        .order_by('-created_at')[:30]
    )

    lines = []
    for u in uploads:
        lines.append(f"• {u.file_name} ({u.file_type}) — uploaded by {u.uploader.full_name}")

    context = (
        f"Class: {class_obj.name}\n"
        f"Description: {class_obj.description or 'None'}\n"
        f"Total members: {class_obj.members.count()}\n\n"
        f"Files in this class ({len(uploads)} total):\n"
        + ("\n".join(lines) if lines else "No files uploaded yet.")
    )
    return context, [u.file_name for u in uploads[:5]]


def get_history(conversation, limit: int = 12) -> list[dict]:
    msgs = list(conversation.messages.order_by('-created_at')[:limit])
    return [{"role": m.role, "content": m.content} for m in reversed(msgs)]


def chat(user_message: str, class_obj, conversation, user) -> dict:
    """Call OpenRouter and return the assistant reply with metadata."""
    client = get_client()
    class_context, source_files = build_class_context(class_obj)
    history = get_history(conversation)

    system_prompt = (
        "You are Kibegi AI — a smart, friendly study assistant built into the Kibegi student platform.\n"
        "You help students understand their class materials, answer academic questions, and explain concepts.\n\n"
        f"{class_context}\n\n"
        "Guidelines:\n"
        "- Be concise, helpful, and friendly — like a smart study partner.\n"
        "- Reference uploaded files by name when relevant.\n"
        "- If something isn't in the class files, say so honestly — don't invent information.\n"
        "- Kenyan/East African academic context is common here.\n"
        "- Respond in the same language the student uses (English or Swahili)."
    )

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    try:
        resp = client.chat.completions.create(
            model=getattr(settings, 'AI_CHAT_MODEL', 'openai/gpt-4o-mini'),
            messages=messages,
            max_tokens=800,
            temperature=0.7,
        )
        reply = resp.choices[0].message.content or ""
        tokens = resp.usage.total_tokens if resp.usage else 0
        return {"response": reply, "tokens_used": tokens, "sources": source_files, "success": True}
    except Exception as exc:
        logger.error("OpenRouter call failed: %s", exc)
        return {
            "response": "I'm having trouble connecting right now. Please try again in a moment.",
            "tokens_used": 0,
            "sources": [],
            "success": False,
        }
