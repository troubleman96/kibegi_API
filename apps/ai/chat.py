import logging
import re
from openai import OpenAI
from django.conf import settings
from django.db.models import Q

from .context import build_platform_context

logger = logging.getLogger(__name__)

AI_REQUEST_TIMEOUT = 60

DEFAULT_MODEL = 'openai/gpt-4o-mini'

PRACTICE_PATTERNS = re.compile(
    r'\b(quiz\s*me|test\s*me|practice|flashcard|examine\s*me|drill|question\s*me|give\s*me\s*(a\s*)?(test|quiz|question))\b',
    re.IGNORECASE,
)


def resolve_api_key(user) -> tuple[str, str]:
    """Return (api_key, model) for a user — their own pasted key wins over the shared one."""
    from .models import UserAIProfile

    try:
        profile = getattr(user, 'ai_profile', None)
        if profile is None:
            profile = UserAIProfile.objects.filter(user=user).first()
    except Exception:
        profile = None

    if profile and profile.has_key:
        return profile.api_key, profile.chat_model.strip() or settings.AI_CHAT_MODEL

    return settings.NGAMIA_API_KEY, settings.AI_CHAT_MODEL


def get_client(api_key: str | None = None) -> OpenAI:
    return OpenAI(
        base_url=getattr(settings, 'NGAMIA_BASE_URL', 'https://api.ngamia.cc/v1'),
        api_key=api_key or settings.NGAMIA_API_KEY,
        timeout=AI_REQUEST_TIMEOUT,
    )


def is_practice_request(message: str) -> bool:
    return bool(PRACTICE_PATTERNS.search(message))


def _class_scope(class_obj, user) -> Q:
    """Return a filter scope over the user's classes for Upload-level retrieval."""
    if class_obj is not None:
        return Q(class_obj=class_obj)
    return Q(class_obj__memberships__user=user)


def _class_ids_for(class_obj, user) -> list:
    if class_obj is not None:
        return [class_obj.id]
    from apps.classes.models import Membership
    return list(
        Membership.objects.filter(user=user).values_list("class_obj_id", flat=True)
    )


def _keyword_search_chunks(user_message: str, class_ids: list, top_k: int = 6):
    from .models import DocumentChunk

    terms = [
        term.lower()
        for term in re.findall(r"[A-Za-z0-9]{3,}", user_message)
        if term.lower() not in {"the", "and", "for", "that", "this", "with", "from"}
    ]
    chunks = list(
        DocumentChunk.objects.filter(
            upload__class_obj_id__in=class_ids,
            upload__is_deleted=False,
        ).select_related("upload").order_by("upload", "chunk_index")[:200]
    )
    if not chunks:
        return []
    if not terms:
        return chunks[:top_k]

    scored = []
    for chunk in chunks:
        content = chunk.content.lower()
        score = sum(content.count(term) for term in terms)
        if score:
            scored.append((score, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [chunk for _, chunk in scored[:top_k]]


def build_rag_context(user_message: str, user, class_obj=None) -> tuple[str, list[str]]:
    """
    Embed the user query, find similar chunks, return injected context + source names.
    Scoped to one class when class_obj is given, otherwise across all the user's classes.
    Falls back to file-list-only context when no chunks exist yet.
    """
    from apps.uploads.models import Upload
    from .embeddings import embed_query, find_similar_chunks

    class_ids = _class_ids_for(class_obj, user)
    scope = _class_scope(class_obj, user)

    uploads = list(
        Upload.objects.filter(is_deleted=False)
        .filter(scope)
        .select_related('uploader')
        .order_by('-created_at')[:30]
    )

    if class_obj is not None:
        base_context = (
            f"Class: {class_obj.name}\n"
            f"Description: {class_obj.description or 'None'}\n"
            f"Total members: {class_obj.members.count()}\n"
        )
    else:
        base_context = (
            "General mode — searching across all the classes the student belongs to.\n"
        )

    if not uploads:
        return base_context + "\nNo files uploaded yet.", []

    file_list = "\n".join(
        f"• {u.file_name} ({u.file_type}) — {u.uploader.full_name}"
        for u in uploads
    )

    try:
        query_embedding = embed_query(user_message)
        similar = find_similar_chunks(query_embedding, class_ids, top_k=6)
    except Exception as exc:
        logger.warning("Vector search failed, falling back to file list: %s", exc)
        similar = []

    if not similar or all(score <= 0 for score, _ in similar):
        keyword_chunks = _keyword_search_chunks(user_message, class_ids, top_k=6)
        if keyword_chunks:
            similar = [(0.0, chunk) for chunk in keyword_chunks]

    if not similar:
        return (
            base_context
            + f"\nFiles in the class:\n{file_list}\n\n"
            + "(No indexed content yet - students can ask about files by name once processed.)"
        ), [u.file_name for u in uploads[:5]]

    # Build context blocks from top chunks
    context_blocks = []
    source_names = []
    seen_uploads = set()
    for sim_score, chunk in similar:
        fname = chunk.upload.file_name
        if fname not in seen_uploads:
            source_names.append(fname)
            seen_uploads.add(fname)
        context_blocks.append(
            f"[Source: {fname} | relevance: {sim_score:.2f}]\n{chunk.content}"
        )

    rag_section = "\n\n---\n\n".join(context_blocks)

    context = (
        base_context
        + f"\nFiles in the class:\n{file_list}\n\n"
        + "=== RELEVANT CONTENT FROM CLASS FILES ===\n\n"
        + rag_section
        + "\n\n=== END OF RETRIEVED CONTENT ==="
    )
    return context, source_names[:5]


def get_history(conversation, limit: int = 12) -> list[dict]:
    msgs = list(conversation.messages.order_by('-created_at')[:limit])
    return [{"role": m.role, "content": m.content} for m in reversed(msgs)]


def build_system_prompt(platform_context: str, class_context: str | None, practice_mode: bool) -> str:
    base = (
        "You are Kibegi AI — a smart, friendly study assistant built into the Kibegi student platform.\n"
        "You help students with their schedule, reminders, assignments, timetables, and understanding "
        "their class materials. You can read the student's Kibegi data below, so answer questions like "
        "\"What's my timetable?\", \"What's due this week?\", or \"Any reminders?\" directly from it.\n"
    )
    if platform_context:
        base += f"\n{platform_context}\n"
    if class_context:
        base += f"\n{class_context}\n"
    base += (
        "\nGuidelines:\n"
        "- Be concise, helpful, and friendly — like a smart study partner.\n"
        "- Use the student's Kibegi data above when answering questions about their schedule, "
        "timetable, assignments, reminders, or files.\n"
        "- Reference uploaded files by name when relevant.\n"
        "- If something isn't in the data, say so honestly — don't invent information.\n"
        "- Kenyan/East African academic context is common here.\n"
        "- Respond in the same language the student uses (English or Swahili).\n"
        "- When content from files is provided above, use it directly in your answers.\n"
    )
    if practice_mode:
        base += (
            "\nPRACTICE MODE: The student wants to be tested or quizzed.\n"
            "- Generate 3-5 questions from the class content provided.\n"
            "- Mix question types: MCQ, short answer, true/false.\n"
            "- After asking, wait for answers before giving feedback.\n"
            "- Keep questions focused on what's in the uploaded notes.\n"
        )
    return base


def chat(user_message: str, class_obj, conversation, user) -> dict:
    """Call the Ngamia gateway with RAG + platform context and return the assistant reply."""
    api_key, model = resolve_api_key(user)
    client = get_client(api_key)
    practice_mode = is_practice_request(user_message)

    platform_context = build_platform_context(user, class_obj)
    class_context, source_files = build_rag_context(user_message, user, class_obj)

    history = get_history(conversation)
    system_prompt = build_system_prompt(platform_context, class_context, practice_mode)

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    try:
        resp = client.chat.completions.create(
            model=model or DEFAULT_MODEL,
            messages=messages,
            max_tokens=1200 if practice_mode else 800,
            temperature=0.7,
        )
        reply = resp.choices[0].message.content or ""
        tokens = resp.usage.total_tokens if resp.usage else 0
        return {
            "response": reply,
            "tokens_used": tokens,
            "sources": source_files,
            "success": True,
            "practice_mode": practice_mode,
        }
    except Exception as exc:
        logger.error("Ngamia gateway call failed: %s", exc, exc_info=True)
        return {
            "response": "I'm having trouble connecting right now. Please try again in a moment.",
            "tokens_used": 0,
            "sources": [],
            "success": False,
            "practice_mode": False,
        }
