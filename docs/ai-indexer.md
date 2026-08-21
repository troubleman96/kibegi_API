# FastAPI AI Indexer

## Purpose

`services/ai-indexer` is a Python FastAPI sidecar for document ingestion. It restores the non-HTTP AI indexing capability that formerly ran inside the backend, while keeping the public API and domain writes in Go. The service reads the existing upload and AI tables and uses the existing MinIO/S3 object keys.

## Components

| File | Responsibility |
|---|---|
| `app/config.py` | Pydantic settings and environment defaults. |
| `app/db.py` | PostgreSQL pool and AI/upload repository operations. |
| `app/extract.py` | Supported-format extraction and compatibility chunking. |
| `app/worker.py` | Locking, downloads, embeddings, job orchestration, and retries. |
| `app/main.py` | FastAPI lifecycle, health, job status, single-upload, and batch endpoints. |
| `app/worker_runner.py` | Optional continuous polling loop for pending/stale jobs. |
| `tests/test_extract.py` | Deterministic extractor and chunking tests. |

## Processing lifecycle

1. Go receives a multipart upload and writes the MinIO/S3 object.
2. Go inserts the `uploads_upload` row and returns the upload response.
3. Go asynchronously calls `POST /v1/index/uploads/{upload_id}`.
4. The indexer loads the upload row and skips deleted or unsupported records.
5. A Redis lock named with the upload UUID prevents duplicate concurrent processing.
6. The indexer creates or resets the `ai_aiprocessingjob` row to `processing`.
7. The object is downloaded with `MAX_DOWNLOAD_BYTES` protection.
8. Text is extracted and split into overlapping chunks.
9. Existing chunks are deleted and replaced in a PostgreSQL transaction.
10. Embeddings are generated in batches when the provider is configured.
11. The job becomes `done`, or `failed` with a bounded error message.

The process is idempotent. Completed jobs with existing chunks are skipped unless `force=true`; stale processing jobs are eligible for retry after `JOB_STALE_MINUTES`; and failed jobs are selected by the batch endpoint and polling runner.

## Supported formats

| Format | Implementation |
|---|---|
| PDF | `pypdf` page text extraction. |
| DOCX | `python-docx` paragraphs and tables. |
| DOC | LibreOffice headless conversion to text. |
| TXT/Markdown/RTF | UTF-8 with replacement and Latin-1 fallback. |
| CSV | CSV parsing and row normalization. |
| PPTX | `python-pptx` slide and shape text. |
| PPT | LibreOffice headless conversion to text. |
| XLSX | `openpyxl` read-only workbook and sheet extraction. |
| XLS | LibreOffice headless conversion to text. |

A file is eligible when its `file_type` is `document`, `spreadsheet`, or `presentation`, or its extension is in the supported extension set. Images, videos, audio, archives, and unsupported binary files are skipped without creating misleading chunks.

## Chunking and embeddings

Chunking defaults to 1,200 characters with 150 characters of overlap. The splitter prefers paragraph, line, and sentence boundaries after the midpoint of a chunk. The token-count field follows the compatibility approximation `max(1, len(content) // 4)`.

Embeddings use the configured Ngamia-compatible OpenAI endpoint and model. The service processes batches of `EMBEDDING_BATCH_SIZE`. If no key is configured or a batch fails, it writes zero vectors with the expected dimensionality. This preserves text retrieval and job completion rather than losing all extracted content because embeddings are temporarily unavailable.

## Endpoints

| Method | Path | Behavior |
|---|---|---|
| `GET` | `/health` | Reports service, database, storage, and Redis readiness. |
| `GET` | `/v1/index/jobs/{upload_id}` | Returns the existing processing job. |
| `POST` | `/v1/index/uploads/{upload_id}` | Processes one upload; body may include `force`. |
| `POST` | `/v1/index/process-due` | Processes pending, failed, and stale jobs; body may include `limit` and `include_done`. |

Protected endpoints require `Authorization: Bearer <SERVICE_TOKEN>` when `SERVICE_TOKEN` is configured. Missing database/storage configuration results in `503` on operations that require the unavailable dependency.

## Deployment modes

The preferred mode is the Go callback plus a periodic polling runner for recovery. The callback provides low latency and the runner handles missed callbacks, process restarts, failed jobs, and stale processing states. Run only one or carefully coordinated runner per environment unless Redis is configured and healthy.

## Operational diagnosis

If a job is `failed`, inspect the indexer log using the upload UUID, check MinIO object existence using the `file` column, check file size against `MAX_DOWNLOAD_BYTES`, test the extractor locally, and verify provider credentials. If a job remains `processing`, wait for the stale threshold or explicitly force a retry after confirming no active worker is still processing it. If chunks exist but AI answers are weak, inspect extraction quality first, then embedding provider status and vector dimensions.
