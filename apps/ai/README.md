# Kibegi AI App

The `apps/ai` Django app powers the Kibegi study helper. It connects uploaded class materials to an AI chat experience so students can ask questions about PDFs, Word documents, notes, slides, spreadsheets, and other extractable study files.

The app has two main jobs:

1. **Index uploaded class files** into searchable text chunks.
2. **Use those chunks during chat** so the AI answers from the class materials instead of only from general knowledge.

This README explains the full flow from upload to extraction, chunking, embedding, storage, retrieval, chat response, and troubleshooting.

## Important Files

| File | Purpose |
| --- | --- |
| `apps.py` | Registers the AI app and connects signals on app startup. |
| `signals.py` | Listens for new `Upload` records and starts AI processing after the upload transaction commits. |
| `processing.py` | Main upload processing pipeline: open file, extract text, chunk text, save chunks, generate embeddings, update job status. |
| `extraction.py` | Extracts text from supported file types such as PDF, DOCX, TXT, CSV, PPTX, and XLSX. |
| `embeddings.py` | Calls OpenRouter embeddings and searches stored chunks by cosine similarity. |
| `chat.py` | Builds RAG context, retrieves relevant chunks, calls the chat model, and returns the AI response. |
| `models.py` | Stores AI conversations, messages, usage, document chunks, and processing jobs. |
| `views.py` | REST endpoints for chat, conversations, usage, processing status, and manual reprocessing. |
| `management/commands/process_ai_uploads.py` | CLI command for processing/retrying uploads outside the request cycle. |

## High-Level Flow

```text
User uploads a class file
        |
        v
apps.uploads creates an Upload row
        |
        v
apps.ai.signals sees the new Upload after DB commit
        |
        v
apps.ai.processing starts a background thread
        |
        v
File is opened from storage: local filesystem or MinIO/S3
        |
        v
Text is extracted from PDF/DOCX/TXT/CSV/PPTX/XLSX
        |
        v
Text is split into overlapping chunks
        |
        v
Chunks are saved immediately in DocumentChunk
        |
        v
OpenRouter embeddings are requested for those chunks
        |
        v
Embeddings are saved back onto DocumentChunk rows
        |
        v
Student asks a question in AI chat
        |
        v
Question is embedded and matched to class chunks
        |
        v
If vector search is weak/unavailable, keyword chunk search is used
        |
        v
Relevant class file content is injected into the AI prompt
        |
        v
OpenRouter chat model returns the answer
```

## Step 1: Upload Creates an `Upload`

Uploads are handled by the `apps.uploads` app, not directly by `apps.ai`.

A user uploads a file through:

```text
POST /api/v1/uploads/
```

The upload must belong to a class through `class_obj`. The AI app only indexes files that are attached to a class, because the chat experience is class-based.

The `Upload` model stores fields such as:

| Field | Meaning |
| --- | --- |
| `file` | Actual uploaded file path/storage object. |
| `file_name` | Display/original file name. |
| `file_type` | Detected category like `document`, `spreadsheet`, `presentation`, `image`, etc. |
| `class_obj` | Class that owns this file. |
| `uploader` | User who uploaded it. |
| `is_deleted` | Soft-delete flag. Deleted files are ignored by AI retrieval. |

## Step 2: Signal Starts AI Processing

When an `Upload` row is created, `apps.ai.signals` receives the `post_save` event.

Relevant file:

```text
apps/ai/signals.py
```

Important behavior:

```python
transaction.on_commit(lambda: process_upload_async(str(instance.pk)))
```

Processing starts **after the upload transaction commits**. This matters because the background thread should only read the upload after the database row is fully saved.

The signal only starts processing when `should_process(upload)` returns `True`.

## Step 3: File Type Check

The processor decides whether a file is worth indexing through `should_process()` in:

```text
apps/ai/processing.py
```

Supported categories:

```python
EXTRACTABLE_TYPES = {"document", "spreadsheet", "presentation"}
```

Supported extensions:

```python
pdf, docx, doc, txt, md, rtf, csv, pptx, ppt, xlsx, xls
```

Images, videos, audio, and archives are not currently indexed for AI chat.

## Step 4: Background Processing Starts

The upload processor starts in a background thread:

```python
process_upload_async(upload_id)
```

This avoids making the user wait for extraction and embedding during the upload request.

The thread calls:

```python
_process_upload(upload_id)
```

The thread also closes old database connections before and after work. This is important because Django database connections should not be reused unsafely across long-running background threads.

## Step 5: `AIProcessingJob` Tracks Status

Every processable upload gets an `AIProcessingJob` row.

Model:

```text
apps.ai.models.AIProcessingJob
```

Statuses:

| Status | Meaning |
| --- | --- |
| `pending` | Job exists but has not started or was manually reset. |
| `processing` | The pipeline is currently trying to process the file. |
| `done` | Processing finished. May have chunks or may have zero chunks with an explanation. |
| `failed` | Processing raised an exception. Check `error_message`. |

Fields:

| Field | Meaning |
| --- | --- |
| `upload` | One-to-one link to the uploaded file. |
| `status` | Current processing status. |
| `chunks_created` | Number of `DocumentChunk` rows created for this upload. |
| `error_message` | Failure reason or explanation for zero extracted text. |
| `updated_at` | Used to detect stale stuck jobs. |

### Stale Processing Jobs

A job in `processing` for more than 15 minutes is considered stale:

```python
STALE_PROCESSING_AFTER = timedelta(minutes=15)
```

Stale jobs can be retried. This protects against cases where the server restarts, a background thread dies, storage hangs, or an API call never completes cleanly.

## Step 6: Opening the File From Storage

The processor opens the uploaded file using the `FileField` storage backend:

```python
with upload.file.open("rb") as file_handle:
    file_bytes = file_handle.read()
```

This supports both:

- local filesystem storage in development
- MinIO/S3-compatible storage in production

The project also configures S3 client timeouts in `kibegi_api/settings.py`:

```python
AWS_S3_CLIENT_CONFIG = Config(
    connect_timeout=10,
    read_timeout=30,
    retries={"max_attempts": 2},
    s3={"addressing_style": AWS_S3_ADDRESSING_STYLE},
)
```

These prevent object storage calls from hanging forever.

## Step 7: Text Extraction

Text extraction is implemented in:

```text
apps/ai/extraction.py
```

Main function:

```python
extract_text(file_obj, file_name)
```

It chooses the extractor based on file extension.

| Extension | Extractor | Library/Method |
| --- | --- | --- |
| `.pdf` | `_extract_pdf()` | `pdfplumber` |
| `.docx`, `.doc` | `_extract_docx()` | `python-docx` |
| `.txt`, `.md`, `.rtf` | `_extract_text_plain()` | UTF-8 or latin-1 decode |
| `.csv` | `_extract_csv()` | Python `csv` module |
| `.pptx`, `.ppt` | `_extract_pptx()` | `python-pptx` |
| `.xlsx`, `.xls` | `_extract_xlsx()` | `openpyxl` |

If extraction fails, the extractor logs a warning and returns an empty string.

### Important PDF Limitation

`pdfplumber` extracts text that is actually embedded in the PDF.

It does **not** perform OCR.

So this works:

- normal text PDF
- exported lecture notes
- generated PDFs
- selectable text PDFs

This may not work:

- scanned paper PDFs
- image-only PDFs
- screenshots saved as PDFs

For scanned/image-only PDFs, the next improvement would be OCR using something like Tesseract, AWS Textract, Google Document AI, or another OCR provider.

## Step 8: Chunking Text

After text is extracted, it is split into overlapping chunks by:

```python
chunk_text(text, chunk_size=1200, overlap=150)
```

Why chunking is needed:

- Full documents may be too large to put into one AI prompt.
- Search works better on smaller passages.
- Overlap keeps context from being lost between chunks.

Default behavior:

| Setting | Value | Meaning |
| --- | --- | --- |
| `chunk_size` | `1200` characters | Approximate passage size. |
| `overlap` | `150` characters | Repeated tail from previous chunk. |

The chunker tries to split on natural boundaries such as:

- blank lines
- new lines
- sentence endings like `.`, `?`, `!`

## Step 9: Saving `DocumentChunk` Rows

Extracted chunks are stored in:

```text
apps.ai.models.DocumentChunk
```

Fields:

| Field | Meaning |
| --- | --- |
| `upload` | Source uploaded file. |
| `chunk_index` | Position of the chunk inside the file. |
| `content` | Extracted text content. |
| `embedding` | Vector list from the embedding model. May be empty until embeddings succeed. |
| `token_count` | Approximate token count. |

Important design decision:

```text
Text chunks are saved before embeddings are requested.
```

This means the AI helper can still use document text through keyword fallback even if embeddings are slow, unavailable, or fail.

The processing order is now:

```text
extract text
-> split chunks
-> save chunks with empty embeddings
-> call embedding API
-> update chunks with embeddings
```

This is intentional. It keeps the AI useful even when vector search is temporarily unavailable.

## Step 10: Embedding Generation

Embeddings are generated in:

```text
apps/ai/embeddings.py
```

Embedding model:

```python
EMBEDDING_MODEL = "openai/text-embedding-3-small"
```

Provider client:

```python
OpenAI(
    base_url=settings.OPENROUTER_BASE_URL,
    api_key=settings.OPENROUTER_API_KEY,
    timeout=30,
)
```

The app calls OpenRouter using the OpenAI-compatible client.

Chunks are embedded in batches:

```python
BATCH_SIZE = 20
```

If embedding fails for a batch, the current behavior is:

```python
all_embeddings.extend([[0.0] * EMBEDDING_DIMS] * len(batch))
```

That means:

- chunks are not lost
- position alignment is preserved
- vector similarity for those chunks will be useless because zero vectors have no semantic meaning
- chat can still fall back to keyword chunk search

## Step 11: Chat Request

The main chat endpoint is:

```text
POST /api/v1/ai/chat/
```

Request body:

```json
{
  "class_id": "class-uuid",
  "message": "Explain topic one from the uploaded PDF",
  "conversation_id": "optional-existing-conversation-uuid"
}
```

Validation in `AIChatView`:

1. User must be authenticated.
2. `class_id` is required.
3. `message` is required.
4. Message must be 2000 characters or fewer.
5. User must be a member of the class.
6. User must be within their daily AI token limit.

If no `conversation_id` is supplied, a new `AIConversation` is created.

The user message is stored as an `AIMessage` before the AI call.

## Step 12: Usage Limit

Usage is tracked by:

```text
apps.ai.models.AIUsage
```

Fields:

| Field | Meaning |
| --- | --- |
| `tokens_used_today` | Tokens used today. |
| `tokens_used_total` | Lifetime token usage. |
| `daily_limit` | Default daily token limit. |
| `last_reset` | Date when daily usage was last reset. |

Default daily limit:

```python
50000
```

Configured in settings as:

```python
AI_DAILY_TOKEN_LIMIT
```

Note: the model default is currently `50000`. The settings value is available, but the model default is what new `AIUsage` rows use unless code explicitly passes another value.

## Step 13: Building RAG Context

The chat logic lives in:

```text
apps/ai/chat.py
```

Main function:

```python
chat(user_message, class_obj, conversation, user)
```

Before calling the AI model, the app builds context with:

```python
build_rag_context(user_message, class_obj)
```

RAG means Retrieval Augmented Generation. In simple terms:

```text
Search class files first, then give relevant file content to the AI model.
```

The base context always includes:

- class name
- class description
- total class members
- list of recent uploaded files

Then it tries to retrieve relevant chunks from uploaded files.

## Step 14: Vector Search

Vector search flow:

```text
student question
-> embed question
-> load all chunks for this class
-> compare question embedding with chunk embeddings
-> sort by cosine similarity
-> take top 6 chunks
```

Implemented by:

```python
embed_query(user_message)
find_similar_chunks(query_embedding, class_obj, top_k=6)
```

`find_similar_chunks()` only searches chunks where:

```python
upload__class_obj = class_obj
upload__is_deleted = False
```

So the AI does not retrieve deleted files or files from other classes.

Cosine similarity is computed in Python using NumPy. The project does not require `pgvector`.

## Step 15: Keyword Fallback Search

If vector search returns no chunks, or all similarity scores are `0`, the app falls back to keyword search:

```python
_keyword_search_chunks(user_message, class_obj, top_k=6)
```

This searches the stored `DocumentChunk.content` text directly.

Why this exists:

- embeddings may fail
- embeddings may still be processing
- OpenRouter may be slow
- zero-vector embeddings are not useful
- extracted text can still answer many questions

Keyword fallback means the AI helper can still interact with uploaded documents as soon as text chunks exist, even before good embeddings exist.

## Step 16: Prompt Construction

The retrieved chunks are inserted into the system prompt.

The prompt includes a section like:

```text
=== RELEVANT CONTENT FROM CLASS FILES ===

[Source: filename.pdf | relevance: 0.83]
Extracted text chunk here...

---

[Source: another-file.docx | relevance: 0.71]
More extracted text...

=== END OF RETRIEVED CONTENT ===
```

The system prompt tells the model:

- act as Kibegi AI
- help students understand class materials
- reference uploaded files by name
- do not invent content that is not in the class files
- respond in the same language as the student
- use uploaded content directly when provided

## Step 17: Practice Mode

`chat.py` detects practice/quiz requests using `PRACTICE_PATTERNS`.

Examples that trigger practice mode:

- `quiz me`
- `test me`
- `practice`
- `flashcard`
- `examine me`
- `give me a quiz`

When practice mode is active, the prompt asks the model to generate 3-5 questions from the class content and wait for the student's answers.

The API response includes:

```json
{
  "practice_mode": true
}
```

## Step 18: Chat Model Call

The final chat call uses OpenRouter through the OpenAI-compatible client:

```python
client.chat.completions.create(
    model=settings.AI_CHAT_MODEL,
    messages=messages,
    max_tokens=1200 if practice_mode else 800,
    temperature=0.7,
)
```

Default chat model:

```python
AI_CHAT_MODEL = "openai/gpt-4o-mini"
```

The returned response is saved as an assistant `AIMessage`.

The API returns:

```json
{
  "conversation_id": "uuid",
  "response": "AI answer here",
  "sources": ["file1.pdf", "file2.docx"],
  "tokens_used": 1234,
  "practice_mode": false,
  "usage": {
    "tokens_today": 1234,
    "daily_limit": 50000
  }
}
```

## Data Models

### `AIConversation`

One chat thread for one user in one class.

Important fields:

| Field | Meaning |
| --- | --- |
| `user` | Owner of the chat. |
| `class_obj` | Class the chat belongs to. |
| `title` | Usually generated from the first message. |
| `updated_at` | Used for sorting recent conversations. |

### `AIMessage`

One message inside a conversation.

Important fields:

| Field | Meaning |
| --- | --- |
| `conversation` | Parent conversation. |
| `role` | `user` or `assistant`. |
| `content` | Message text. |
| `sources` | File names used for an assistant response. |
| `tokens_used` | Token usage for assistant response. |

### `AIUsage`

Tracks per-user AI token usage.

Important methods:

| Method | Meaning |
| --- | --- |
| `reset_if_needed()` | Resets daily counter when the date changes. |
| `can_use_ai()` | Checks if user is under the daily limit. |
| `record_usage(tokens)` | Adds usage after a successful model response. |

### `DocumentChunk`

Stores extracted text from uploaded files.

This is the most important model for document-aware chat.

A file with 10 chunks creates 10 rows.

### `AIProcessingJob`

Tracks whether a file has been indexed.

This is the main model to inspect when uploads are not becoming interactive.

## API Endpoints

Base path:

```text
/api/v1/ai/
```

### Chat

```text
POST /api/v1/ai/chat/
```

Starts or continues a conversation and returns an AI response.

### List Conversations

```text
GET /api/v1/ai/conversations/?class_id=<uuid>
```

Returns recent conversations for the authenticated user. Optional `class_id` filters by class.

### Conversation Detail

```text
GET /api/v1/ai/conversations/<conversation_id>/
DELETE /api/v1/ai/conversations/<conversation_id>/
```

Returns or deletes a conversation owned by the authenticated user.

### Usage

```text
GET /api/v1/ai/usage/
```

Returns daily and lifetime token usage.

### Processing Status

```text
GET /api/v1/ai/status/<upload_id>/
```

Returns AI processing status for an upload.

Response examples:

```json
{
  "upload_id": "uuid",
  "file_name": "lecture.pdf",
  "status": "done",
  "chunks_created": 12,
  "error_message": null,
  "updated_at": "2026-06-15T09:00:00Z"
}
```

```json
{
  "upload_id": "uuid",
  "file_name": "scan.pdf",
  "status": "done",
  "chunks_created": 0,
  "error_message": "No extractable text found (possibly scanned image or unsupported format)",
  "updated_at": "2026-06-15T09:00:00Z"
}
```

### Manual Reprocessing

```text
POST /api/v1/ai/status/<upload_id>/
```

Manually resets the upload's `AIProcessingJob` to `pending` and starts background processing again.

Only class members can check or trigger processing for a class upload.

## Management Command

The AI app includes a CLI command for processing/retrying uploads:

```text
python manage.py process_ai_uploads
```

Examples:

Process uploads that need normal processing:

```bash
.venv/bin/python manage.py process_ai_uploads --limit 20
```

Retry stale jobs stuck in `processing` longer than 15 minutes:

```bash
.venv/bin/python manage.py process_ai_uploads --retry-stuck --limit 20
```

Retry failed jobs:

```bash
.venv/bin/python manage.py process_ai_uploads --failed --limit 20
```

Force reprocess every supported upload:

```bash
.venv/bin/python manage.py process_ai_uploads --all --limit 20
```

Process one specific upload:

```bash
.venv/bin/python manage.py process_ai_uploads --upload-id <upload-uuid>
```

## Environment Settings

Relevant settings live in:

```text
kibegi_api/settings.py
```

### OpenRouter

```env
OPENROUTER_API_KEY=...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
AI_CHAT_MODEL=openai/gpt-4o-mini
AI_DAILY_TOKEN_LIMIT=50000
```

Used by:

- `apps/ai/embeddings.py`
- `apps/ai/chat.py`

### Storage / MinIO / S3

```env
MINIO_ENABLED=True
MINIO_API_ENDPOINT=...
MINIO_ACCESS_KEY=...
MINIO_SECRET_KEY=...
MINIO_BUCKET=...
MINIO_SECURE=True
MINIO_PUBLIC_BASE_URL=...
AWS_S3_CONNECT_TIMEOUT=10
AWS_S3_READ_TIMEOUT=30
AWS_S3_MAX_ATTEMPTS=2
```

Used when opening uploaded files for text extraction.

## Logging

AI logs are routed through the `apps.ai` logger in `kibegi_api/settings.py`.

This is important because upload processing happens in background threads. Without logging, a job can appear stuck with no visible explanation.

Useful log messages include:

```text
process_upload: upload <id> not found
process_upload: skipping unsupported type for <file>
process_upload: already processing <file>
process_upload: <file> -> <n> chunks
process_upload: done - <file>, <n> chunks stored
process_upload: failed for <file>: <error>
Embedding API failed for batch <n>: <error>
Vector search failed, falling back to file list: <error>
```

## Common Failure Modes

### 1. Job Stuck at `processing`

Symptoms:

```text
status = processing
chunks_created = 0
error_message = ""
```

Possible causes:

- server restarted while background thread was running
- object storage read hung or failed slowly
- network problem reading file from MinIO/S3
- OpenRouter request hung before timeout changes
- process was killed before job status updated

Fix:

```bash
.venv/bin/python manage.py process_ai_uploads --retry-stuck --limit 20
```

### 2. Job Done With Zero Chunks

Symptoms:

```text
status = done
chunks_created = 0
error_message = "No extractable text found..."
```

Possible causes:

- scanned PDF
- image-only PDF
- unsupported document structure
- corrupt file
- empty file

Fix options:

- upload a text-based PDF
- upload DOCX/TXT version
- add OCR support to the AI pipeline

### 3. Chunks Exist But Embeddings Are Empty or Zero

Symptoms:

- `DocumentChunk` rows exist
- `embedding` is `[]` or zero vectors
- chat still may work through keyword fallback

Possible causes:

- OpenRouter key invalid
- OpenRouter out of credits
- embedding model unavailable
- network timeout
- provider rejects embedding request

Fix:

- check `OPENROUTER_API_KEY`
- check OpenRouter account/credits/model support
- inspect `apps.ai` logs
- rerun processing after fixing provider issue

### 4. Chat Mentions Files But Does Not Answer From Content

Possible causes:

- chunks were not created yet
- uploaded file has no extractable text
- user asked about content that is not in the files
- vector search returned no relevant chunks and keyword fallback found no matching terms

Check:

```bash
.venv/bin/python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','kibegi_api.settings'); import django; django.setup(); from apps.ai.models import DocumentChunk; print(DocumentChunk.objects.count())"
```

Also check a specific upload through:

```text
GET /api/v1/ai/status/<upload_id>/
```

### 5. Unsupported File Type

Images, videos, audio, and archives are valid platform uploads, but they are not AI-indexed right now.

Examples not indexed:

- `.png`
- `.jpg`
- `.mp4`
- `.mp3`
- `.zip`

## Production Debug Checklist

When a user says: "I uploaded a PDF but AI cannot answer from it," check this sequence.

### 1. Confirm Upload Exists

Check the upload in the database/admin/API and confirm:

- `is_deleted = False`
- `class_obj` is set
- file name has supported extension
- file can be downloaded/opened

### 2. Check Processing Status

```text
GET /api/v1/ai/status/<upload_id>/
```

Interpretation:

| Status | Meaning |
| --- | --- |
| `not_started` | Signal may not have fired, file unsupported, or job missing. Try manual POST. |
| `pending` | Job exists but has not processed yet. |
| `processing` | Wait briefly; if older than 15 minutes, retry stale jobs. |
| `done` + chunks > 0 | File should be usable by AI. |
| `done` + chunks = 0 | Extraction found no text. Likely scanned/empty/unsupported content. |
| `failed` | Read `error_message`. |

### 3. Retry If Needed

```bash
.venv/bin/python manage.py process_ai_uploads --retry-stuck --limit 10
.venv/bin/python manage.py process_ai_uploads --failed --limit 10
```

### 4. Check Chunk Count

```bash
.venv/bin/python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','kibegi_api.settings'); import django; django.setup(); from apps.uploads.models import Upload; u=Upload.objects.get(id='<upload-id>'); print(u.file_name, u.chunks.count())"
```

### 5. Check Logs

Look for `apps.ai` log entries around the upload time.

Common things to look for:

- storage timeout
- permission/access denied from S3/MinIO
- no extractable text
- OpenRouter errors
- embedding API failures

## Why Processing Power Is Usually Not the Problem

The current AI pipeline is not very CPU-heavy for normal text PDFs and DOCX files.

Most work is I/O-bound or API-bound:

| Step | Main bottleneck |
| --- | --- |
| Reading file | MinIO/S3/network/storage |
| Extracting PDF text | Moderate CPU for large PDFs, usually manageable |
| Chunking text | Very light CPU |
| Embeddings | External OpenRouter API/network/provider limits |
| Chat | External OpenRouter API/network/provider limits |

Server processing power may matter for very large PDFs, many simultaneous uploads, or future OCR. But for normal documents, failures are more likely from:

- storage read problems
- OpenRouter/API problems
- scanned PDFs with no text
- background thread interruption

## Current Guarantees and Limitations

### What Works

- Supported document uploads automatically trigger AI indexing.
- Text chunks are saved before embedding calls.
- Chat can use vector search when embeddings are good.
- Chat can use keyword fallback when embeddings are missing/zero.
- Stale jobs can be retried.
- Existing stuck files can be reprocessed through CLI or API.

### What Does Not Yet Work

- OCR for scanned PDFs/images.
- True async queue durability with Celery/RQ. Current implementation uses daemon threads.
- Large-scale vector indexing with pgvector or a vector DB.
- Per-file progress percentages beyond status/chunk count.

## Recommended Future Improvements

1. Replace daemon threads with Celery/RQ/background workers.
2. Add OCR for scanned PDFs.
3. Store embedding status separately from extraction status.
4. Add an admin page for AI processing jobs.
5. Add a scheduled retry job for stale `processing` jobs.
6. Add tests for PDF extraction, chunk creation, fallback retrieval, and manual reprocessing.
7. Add frontend polling after upload using `/api/v1/ai/status/<upload_id>/`.

## Quick Mental Model

The AI does not read PDFs directly during chat.

Instead:

```text
PDF -> extracted text -> DocumentChunk rows -> retrieved chunks -> AI prompt -> answer
```

The most important table for document-aware AI is:

```text
DocumentChunk
```

If a file has `DocumentChunk` rows, the AI has text it can use.

If a file has no chunks, the AI can only see the file name and metadata, not the document content.
