"""
Background pipeline: Upload → extract text → chunk → embed → store as DocumentChunks.
Uses daemon threads (same pattern as apps.sharing.tasks).
"""
import io
import logging
import threading

from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)

# File types we can extract text from
EXTRACTABLE_TYPES = {'document', 'spreadsheet', 'presentation'}
EXTRACTABLE_EXTENSIONS = {
    'pdf', 'docx', 'doc', 'txt', 'md', 'rtf',
    'csv', 'pptx', 'ppt', 'xlsx',
}


def should_process(upload) -> bool:
    """Return True if this upload type is worth processing."""
    import os
    ext = os.path.splitext(upload.file_name)[1].lower().lstrip('.')
    return upload.file_type in EXTRACTABLE_TYPES or ext in EXTRACTABLE_EXTENSIONS


def process_upload_async(upload_id: str):
    """Fire-and-forget: trigger processing in a background thread."""
    thread = threading.Thread(
        target=_process_upload,
        args=(upload_id,),
        daemon=True,
    )
    thread.start()


def _process_upload(upload_id: str):
    """
    Full pipeline for one upload:
    1. Load file from storage
    2. Extract text
    3. Chunk text
    4. Generate embeddings
    5. Store DocumentChunks
    6. Update AIProcessingJob status
    """
    # Only call setup if not already initialised (standalone scripts).
    # When called from a live Django process the apps registry is already ready.
    from django.apps import apps as django_apps
    if not django_apps.ready:
        import django
        django.setup()

    from apps.uploads.models import Upload
    from .models import AIProcessingJob, DocumentChunk
    from .extraction import extract_text, chunk_text
    from .embeddings import embed_texts

    try:
        upload = Upload.objects.select_related('uploader', 'class_obj').get(pk=upload_id)
    except Upload.DoesNotExist:
        logger.warning("process_upload: upload %s not found", upload_id)
        return

    if not should_process(upload):
        logger.info("process_upload: skipping unsupported type for %s", upload.file_name)
        return

    job, _ = AIProcessingJob.objects.get_or_create(upload=upload)
    if job.status == AIProcessingJob.STATUS_DONE:
        logger.info("process_upload: already done for %s", upload.file_name)
        return

    job.status = AIProcessingJob.STATUS_PROCESSING
    job.error_message = ''
    job.save(update_fields=['status', 'error_message'])

    try:
        # 1. Open file from storage (MinIO in prod, filesystem in dev)
        file_handle = default_storage.open(upload.file.name, 'rb')
        file_bytes = file_handle.read()
        file_handle.close()

        # 2. Extract text
        text = extract_text(io.BytesIO(file_bytes), upload.file_name)
        if not text.strip():
            job.status = AIProcessingJob.STATUS_DONE
            job.chunks_created = 0
            job.error_message = 'No extractable text found (possibly scanned image or unsupported format)'
            job.save(update_fields=['status', 'chunks_created', 'error_message'])
            logger.info("process_upload: no text in %s", upload.file_name)
            return

        # 3. Chunk
        chunks = chunk_text(text)
        if not chunks:
            job.status = AIProcessingJob.STATUS_DONE
            job.chunks_created = 0
            job.save(update_fields=['status', 'chunks_created'])
            return

        logger.info("process_upload: %s → %d chunks", upload.file_name, len(chunks))

        # 4. Embed (in batches)
        embeddings = embed_texts(chunks)

        # 5. Delete old chunks for this upload (re-process)
        DocumentChunk.objects.filter(upload=upload).delete()

        # 6. Bulk-create new chunks
        to_create = []
        for i, (chunk_text_content, embedding) in enumerate(zip(chunks, embeddings)):
            to_create.append(DocumentChunk(
                upload=upload,
                chunk_index=i,
                content=chunk_text_content,
                embedding=embedding,
                token_count=len(chunk_text_content) // 4,  # approx
            ))
        DocumentChunk.objects.bulk_create(to_create)

        job.status = AIProcessingJob.STATUS_DONE
        job.chunks_created = len(to_create)
        job.error_message = ''
        job.save(update_fields=['status', 'chunks_created', 'error_message'])

        logger.info("process_upload: done — %s, %d chunks stored", upload.file_name, len(to_create))

    except Exception as exc:
        logger.error("process_upload: failed for %s: %s", upload.file_name, exc, exc_info=True)
        job.status = AIProcessingJob.STATUS_FAILED
        job.error_message = str(exc)[:500]
        job.save(update_fields=['status', 'error_message'])
