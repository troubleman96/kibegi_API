# Kibegi Deployment Guide

## Recommended topology

Deploy the Go API and agent gateway behind a TLS reverse proxy. Keep the AI indexer, PostgreSQL, Redis, and MinIO/S3 on a private network. A typical hostname layout is `api.kibegi.com` for Go and `agent.kibegi.com` for FastMCP. The indexer should not have a public DNS name.

```text
api.kibegi.com    -> Go API :8080
agent.kibegi.com  -> FastMCP gateway :8091
private DNS       -> AI indexer :8090
private network   -> PostgreSQL, Redis, MinIO/S3
```

## Build artifacts

Build the Go binary with the local toolchain requirement:

```bash
GOTOOLCHAIN=local go build -o bin/kibegi-api ./cmd/kibegi-api/
```

Install Python dependencies in isolated virtual environments for each support service:

```bash
python3 -m venv services/ai-indexer/.venv
services/ai-indexer/.venv/bin/pip install -r services/ai-indexer/requirements.txt

python3 -m venv services/kibegi-agent/.venv
services/kibegi-agent/.venv/bin/pip install -r services/kibegi-agent/requirements.txt
```

Do not copy `.env` files into images. Inject secrets at runtime through systemd environment files, Docker secrets, or a managed secret store.

## Docker Compose shape

A production Compose deployment should define `kibegi-api`, `kibegi-ai-indexer`, and `kibegi-agent` as separate services. The API service depends on the private indexer by network name, for example `AI_INDEXER_URL=http://kibegi-ai-indexer:8090`. The indexer and agent should use their own Python environments or image layers, with health checks for `/health`. PostgreSQL, Redis, and MinIO may be Compose services for development or external managed endpoints for production.

The reverse proxy should expose only the API and agent ports, terminate TLS, set forwarding headers deliberately, enforce request body limits, and preserve `X-Request-ID`. The indexer route should be reachable only from the API container/network and administrative operations should require the indexer service token.

## systemd shape

For a VPS, create three units with separate users or service accounts:

```text
kibegi-api.service
kibegi-ai-indexer.service
kibegi-agent.service
```

The Go unit executes the compiled binary. The indexer unit executes `uvicorn app.main:app --host 127.0.0.1 --port 8090` from its service directory and virtual environment. The agent unit executes the corresponding Uvicorn command on `127.0.0.1:8091`. Use `Restart=on-failure`, a dedicated environment file, a private working directory, and restrictive filesystem permissions.

The optional indexer polling runner can be a separate unit or a scheduled container. Use it when callbacks are not sufficient or when periodic retry sweeps are required. Do not run multiple unrestricted runners without Redis because duplicate processing locks depend on Redis coordination.

## Reverse proxy requirements

The proxy should route `/` or the API hostname to Go and `/mcp` on the agent hostname to the FastMCP gateway. Configure WebSocket/SSE behavior only if the selected FastMCP transport requires it. Forward `Authorization` and `X-Request-ID` headers. Set explicit CORS policy at the Go and agent layers rather than relying only on proxy defaults.

## Deployment sequence

Build and test locally, publish immutable artifacts, apply environment secrets, verify PostgreSQL/Redis/MinIO connectivity, start Go, start the indexer, start the agent, run health checks, then run authenticated read-only smoke tests. Enable write traffic only after checking uploads, AI callback delivery, storage, and a representative MCP tool call. Keep the previous binary and the pre-cleanup Git tag available until the production soak window completes.
