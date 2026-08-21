# `services/ai-indexer/app`

## Module map

| Module | Responsibility |
|---|---|
| `config.py` | Environment-backed settings. |
| `db.py` | Pooled PostgreSQL reads/writes for uploads, jobs, chunks, and histories. |
| `extract.py` | File-type gating, extraction, and overlap-preserving chunking. |
| `worker.py` | Redis locking, object download, embedding batches, job orchestration, and retry results. |
| `main.py` | FastAPI health and protected indexing endpoints. |
| `worker_runner.py` | Optional continuous pending/stale-job polling process. |

## Extension rules

Add a new file format in `extract.py`, with a deterministic unit test and a bounded download/temp-file strategy. Add repository fields in `db.py` only when they already exist in the compatibility schema. Keep job transitions explicit and idempotent. Do not add domain API routes here; Go owns the public AI API.

## Local commands

```bash
cd services/ai-indexer
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8090
python3 -m app.worker_runner
```

Use `SERVICE_TOKEN` for protected endpoint tests and never place real provider credentials in committed files.
