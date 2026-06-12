import logging
import re
from openai import OpenAI
from django.conf import settings

logger = logging.getLogger(__name__)

PRACTICE_PATTERNS = re.compile(
    r'\b(quiz\s*me|test\s*me|practice|flashcard|examine\s*me|drill|question\s*me|give\s*me\s*(a\s*)?(test|quiz|question))\b',
    re.IGNORECASE,
)


def get_client() -> OpenAI:
    return OpenAI(
        base_url=getattr(settings, 'OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1'),
        api_key=settings.OPENROUTER_API_KEY,
        default_headers={
            "HTTP-Referer": "https://kibegi.com",
            "X-Title": "Kibegi AI",
        },
    )


def is_practice_request(message: str) -> bool:
    return bool(PRACTICE_PATTERNS.search(message))


def build_rag_context(user_message: str, class_obj) -> tuple[str, list[str]]:
    """
    Embed the user query, find similar chunks, return injected context + source names.
    Falls back to file-list-only context when no chunks exist yet.
    """
    from apps.uploads.models import Upload
    from .embeddings import embed_query, find_similar_chunks

    uploads = list(
        Upload.objects.filter(class_obj=class_obj, is_deleted=False)
        .select_related('uploader')
        .order_by('-created_at')[:30]
    )

    # Base class info
    base_context = (
        f"Class: {class_obj.name}\n"
        f"Description: {class_obj.description or 'None'}\n"
        f"Total members: {class_obj.members.count()}\n"
    )

    if not uploads:
        return base_context + "\nNo files uploaded yet.", []

    file_list = "\n".join(
        f"• {u.file_name} ({u.file_type}) — {u.uploader.full_name}"
        for u in uploads
    )

    try:
        query_embedding = embed_query(user_message)
        similar = find_similar_chunks(query_embedding, class_obj, top_k=6)
    except Exception as exc:
        logger.warning("Vector search failed, falling back to file list: %s", exc)
        similar = []

    if not similar:
        return (
            base_context
            + f"\nFiles in this class:\n{file_list}\n\n"
            + "(No indexed content yet — students can ask about files by name once processed.)"
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
        + f"\nFiles in this class:\n{file_list}\n\n"
        + "=== RELEVANT CONTENT FROM CLASS FILES ===\n\n"
        + rag_section
        + "\n\n=== END OF RETRIEVED CONTENT ==="
    )
    return context, source_names[:5]


def get_history(conversation, limit: int = 12) -> list[dict]:
    msgs = list(conversation.messages.order_by('-created_at')[:limit])
    return [{"role": m.role, "content": m.content} for m in reversed(msgs)]


def build_system_prompt(class_context: str, practice_mode: bool) -> str:
    base = (
        "You are Kibegi AI — a smart, friendly study assistant built into the Kibegi student platform.\n"
        "You help students understand their class materials, answer academic questions, and explain concepts.\n\n"
        f"{class_context}\n\n"
        "Guidelines:\n"
        "- Be concise, helpful, and friendly — like a smart study partner.\n"
        "- Reference uploaded files by name when relevant.\n"
        "- If something isn't in the class files, say so honestly — don't invent information.\n"
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
    """Call OpenRouter with RAG context and return the assistant reply."""
    client = get_client()
    practice_mode = is_practice_request(user_message)
    class_context, source_files = build_rag_context(user_message, class_obj)
    history = get_history(conversation)

    system_prompt = build_system_prompt(class_context, practice_mode)

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    try:
        resp = client.chat.completions.create(
            model=getattr(settings, 'AI_CHAT_MODEL', 'openai/gpt-4o-mini'),
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
        logger.error("OpenRouter call failed: %s", exc)
        return {
            "response": "I'm having trouble connecting right now. Please try again in a moment.",
            "tokens_used": 0,
            "sources": [],
            "success": False,
            "practice_mode": False,
        }
