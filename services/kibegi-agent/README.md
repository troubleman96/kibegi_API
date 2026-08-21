# Kibegi Agent Gateway

This Python service provides a FastAPI gateway and a FastMCP HTTP server over the migrated Go API. The Go service remains the authoritative backend. The gateway forwards authenticated user JWTs to Go and does not duplicate domain data.

## Interfaces

| Interface | Path | Purpose |
|---|---|---|
| FastAPI health | `GET /health` | Checks the gateway and Go API. |
| FastAPI proxy | `POST /v1/proxy` | Calls an allowlisted `/api/v1/` Go route. Non-GET operations require `confirm: true`. |
| FastMCP HTTP | configured by `MCP_PATH`, default `/mcp` | Exposes typed tools plus an allowlisted generic API tool. |

The generic API tool supports the complete migrated API namespace while preventing calls outside Kibegi routes. End-user JWTs are supplied explicitly to each tool call. Gateway-level access can be protected with `GO_API_SERVICE_TOKEN`; mutation tools additionally require explicit confirmation.

## Run locally

```bash
cd services/kibegi-agent
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8091
```

The FastMCP HTTP endpoint is available at `http://127.0.0.1:8091/mcp` by default. Use a deployment-level authentication proxy or configure an appropriate FastMCP authentication provider before exposing it publicly.
