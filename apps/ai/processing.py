"""
Background pipeline: Upload -> extract text -> chunk -> embed -> store as DocumentChunks.
"""
import io
import logging
import os
import threading
from datetime import timedelta

from django.db import close_old_connections
from django.utils import timezone

logger = logging.getLogger(__name__)

# File types we can extract text from.
EXTRACTABLE_TYPES = {"document", "spreadsheet", "presentation"}
EXTRACTABLE_EXTENSIONS = {
    "pdf", "docx", "doc", "txt", "md", "rtf",
    "csv", "pptx", "ppt", "xlsx", "xls",
}
STALE_PROCESSING_AFTER = timedelta(minutes=15)


def should_process(upload) -> bool:
    """Return True if this upload type is worth processing for AI/RAG."""
    file_name = getattr(upload, "file_name", "") or os.path.basename(getattr(upload.file, "name", ""))
    ext = os.path.splitext(file_name)[1].lower().lstrip(".")
    return upload.file_type in EXTRACTABLE_TYPES or ext in EXTRACTABLE_EXTENSIONS


def process_upload_async(upload_id: str):
    """Fire-and-forget processing for request/response uploads."""
    thread = threading.Thread(
        target=_thread_entrypoint,
        args=(upload_id,),
        daemon=True,
        name=f"ai-upload-{upload_id}",
    )
    thread.start()


def _thread_entrypoint(upload_id: str):
    close_old_connections()
    try:
        _process_upload(upload_id)
    finally:
        close_old_connections()


def _job_is_stale(job) -> bool:
    return job.updated_at <= timezone.now() - STALE_PROCESSING_AFTER


def _process_upload(upload_id: str):
    """Run the full processing pipeline for one uploaded file."""
    from django.apps import apps as django_apps
    if not django_apps.ready:
        import django
        django.setup()

    from apps.uploads.models import Upload
    from .models import AIProcessingJob, DocumentChunk
    from .extraction import extract_text, chunk_text
    from .embeddings import embed_texts

    try:
        upload = Upload.objects.select_related("uploader", "class_obj").get(pk=upload_id)
    except Upload.DoesNotExist:
        logger.warning("process_upload: upload %s not found", upload_id)
        return

    if not should_process(upload):
        logger.info("process_upload: skipping unsupported type for %s", upload.file_name)
        return

    job, _ = AIProcessingJob.objects.get_or_create(upload=upload)

    if job.status == AIProcessingJob.STATUS_PROCESSING and not _job_is_stale(job):
        logger.info("process_upload: already processing %s", upload.file_name)
        return

    if job.status == AIProcessingJob.STATUS_DONE and DocumentChunk.objects.filter(upload=upload).exists():
        logger.info("process_upload: already done for %s", upload.file_name)
        return

    job.status = AIProcessingJob.STATUS_PROCESSING
    job.error_message = ""
    job.save(update_fields=["status", "error_message", "updated_at"])

    try:
        if not upload.file:
            raise ValueError("Upload has no file attached")

        # Use the FileField storage instead of global default_storage so MinIO/local
        # overrides remain correct for this specific file.
        with upload.file.open("rb") as file_handle:
            file_bytes = file_handle.read()

        text = extract_text(io.BytesIO(file_bytes), upload.file_name)
        if not text.strip():
            DocumentChunk.objects.filter(upload=upload).delete()
            job.status = AIProcessingJob.STATUS_DONE
            job.chunks_created = 0
            job.error_message = "No extractable text found (possibly scanned image or unsupported format)"
            job.save(update_fields=["status", "chunks_created", "error_message", "updated_at"])
            logger.info("process_upload: no text in %s", upload.file_name)
            return

        chunks = chunk_text(text)
        if not chunks:
            DocumentChunk.objects.filter(upload=upload).delete()
            job.status = AIProcessingJob.STATUS_DONE
            job.chunks_created = 0
            job.error_message = "Text was extracted but no chunks were generated"
            job.save(update_fields=["status", "chunks_created", "error_message", "updated_at"])
            return

        logger.info("process_upload: %s -> %d chunks", upload.file_name, len(chunks))

        # Store text chunks before calling the embedding API. Even if embeddings are
        # slow or unavailable, chat can still use keyword retrieval over content.
        DocumentChunk.objects.filter(upload=upload).delete()
        to_create = []
        for i, chunk_content in enumerate(chunks):
            to_create.append(DocumentChunk(
                upload=upload,
                chunk_index=i,
                content=chunk_content,
                embedding=[],
                token_count=max(1, len(chunk_content) // 4),
            ))
        created_chunks = DocumentChunk.objects.bulk_create(to_create)
        job.chunks_created = len(created_chunks)
        job.save(update_fields=["chunks_created", "updated_at"])

        embeddings = embed_texts(chunks)
        if len(embeddings) != len(chunks):
            logger.warning(
                "process_upload: embedding count mismatch for %s: %d embeddings for %d chunks",
                upload.file_name,
                len(embeddings),
                len(chunks),
            )

        for i, chunk in enumerate(created_chunks):
            if i < len(embeddings):
                chunk.embedding = embeddings[i]
        DocumentChunk.objects.bulk_update(created_chunks, ["embedding"])

        job.status = AIProcessingJob.STATUS_DONE
        job.chunks_created = len(created_chunks)
        job.error_message = ""
        job.save(update_fields=["status", "chunks_created", "error_message", "updated_at"])

        logger.info("process_upload: done - %s, %d chunks stored", upload.file_name, len(created_chunks))

    except Exception as exc:
        logger.error("process_upload: failed for %s: %s", upload.file_name, exc, exc_info=True)
        job.status = AIProcessingJob.STATUS_FAILED
        job.error_message = str(exc)[:500]
        job.save(update_fields=["status", "error_message", "updated_at"])
