# `services`

This directory contains the two intentional Python services that complement the Go-primary backend. They are independently deployable and must not be merged into the Go domain process.

| Service | Exposure | Role |
|---|---|---|
| `ai-indexer` | Private network, default `:8090` | Asynchronous upload extraction, chunk persistence, optional embeddings, and retry sweeps. |
| `kibegi-agent` | Protected gateway, default `:8091` | FastAPI proxy and FastMCP HTTP tools over the Go API. |

Both services use environment configuration and separate dependency manifests. The indexer may access PostgreSQL, Redis, and MinIO/S3. The agent needs outbound access to the Go API and should not need direct database or object-storage access. Keep Python package changes isolated to the service that owns the behavior, add tests in the service’s `tests/` folder, and update the matching guide under `docs/`.
