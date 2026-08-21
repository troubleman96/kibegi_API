# Kibegi AI Indexer

This standalone FastAPI service processes supported uploads from the existing Kibegi PostgreSQL and MinIO/S3 infrastructure. It preserves the Django AI tables and processing states while allowing the primary Go API to remain the public backend.

## Responsibilities

The service downloads objects referenced by `uploads_upload.file`, extracts text from PDF, DOC/DOCX, TXT, Markdown, RTF, CSV, PPT/PPTX, and XLS/XLSX files, chunks text using the existing 1,200-character and 150-character overlap defaults, writes `ai_documentchunk` rows, optionally generates embeddings through the configured Ngamia-compatible OpenAI endpoint, and updates `ai_aiprocessingjob` states. Embedding failures fall back to zero vectors so text chunks remain available for keyword retrieval.

Redis locks prevent duplicate concurrent processing of the same upload. PostgreSQL remains authoritative for jobs and chunks. The service does not run Django and does not change the schema.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Reports database, storage, and Redis readiness. |
| `GET` | `/v1/index/jobs/{upload_id}` | Reads the existing AI processing job. |
| `POST` | `/v1/index/uploads/{upload_id}` | Processes one upload; accepts `{"force": true}` to retry/reindex. |
| `POST` | `/v1/index/process-due` | Processes pending, failed, and stale jobs; accepts `limit` and `include_done`. |

When `SERVICE_TOKEN` is configured, protected endpoints require `Authorization: Bearer <SERVICE_TOKEN>`.

## Run locally

```bash
cd services/ai-indexer
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8090
```

The service is intentionally separate from Django. Keep the existing Django implementation until the Go API, this indexer, and the later agent/MCP layer have passed end-to-end verification.
