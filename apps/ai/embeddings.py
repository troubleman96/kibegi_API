"""
Embedding generation and similarity search.
Uses the Ngamia gateway (https://api.ngamia.cc/v1) for embeddings. If the
gateway/model doesn't support embeddings, failures are caught and chat falls
back to keyword retrieval over stored chunk content.
Similarity computed with numpy — no pgvector extension needed.
"""
import logging
import numpy as np
from openai import OpenAI
from django.conf import settings

AI_REQUEST_TIMEOUT = 60

logger = logging.getLogger(__name__)

EMBEDDING_DIMS = 1536
BATCH_SIZE = 20  # chunks per API call


def get_client(api_key: str | None = None) -> OpenAI:
    return OpenAI(
        base_url=getattr(settings, 'NGAMIA_BASE_URL', 'https://api.ngamia.cc/v1'),
        api_key=api_key or settings.NGAMIA_API_KEY,
        timeout=AI_REQUEST_TIMEOUT,
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts in batches.
    Returns list of embedding vectors (1536-dim).
    """
    if not texts:
        return []

    client = get_client()
    model = getattr(settings, 'EMBEDDING_MODEL', 'openai/text-embedding-3-small')
    all_embeddings = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i: i + BATCH_SIZE]
        # Clean texts — newlines confuse the model
        batch = [t.replace('\n', ' ').strip() for t in batch]
        try:
            response = client.embeddings.create(
                model=model,
                input=batch,
            )
            batch_embeddings = [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
            all_embeddings.extend(batch_embeddings)
        except Exception as exc:
            logger.error("Embedding API failed for batch %d: %s", i, exc)
            # Return zero vectors for failed batch so we don't lose position
            all_embeddings.extend([[0.0] * EMBEDDING_DIMS] * len(batch))

    return all_embeddings


def embed_query(text: str) -> list[float]:
    """Embed a single query text."""
    results = embed_texts([text])
    return results[0] if results else [0.0] * EMBEDDING_DIMS


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    norm_a = np.linalg.norm(va)
    norm_b = np.linalg.norm(vb)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(va, vb) / (norm_a * norm_b))


def find_similar_chunks(query_embedding: list[float], class_ids: list, top_k: int = 6):
    """
    Find the most relevant DocumentChunks for a query within the given class ids.
    Returns list of (similarity_score, DocumentChunk) tuples, sorted descending.
    """
    from .models import DocumentChunk

    # Load all chunks for non-deleted uploads in these classes
    chunks = list(
        DocumentChunk.objects.filter(
            upload__class_obj_id__in=class_ids,
            upload__is_deleted=False,
        ).select_related('upload').order_by('upload', 'chunk_index')
    )

    if not chunks:
        return []

    # Compute similarity for all chunks
    scored = []
    for chunk in chunks:
        if not chunk.embedding:
            continue
        sim = cosine_similarity(query_embedding, chunk.embedding)
        scored.append((sim, chunk))

    # Sort by similarity descending
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]
