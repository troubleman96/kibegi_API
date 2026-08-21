# `services/kibegi-agent/app`

## Module map

| Module | Responsibility |
|---|---|
| `config.py` | Go API base URL, gateway token, timeouts, MCP path, and origin settings. |
| `client.py` | Async upstream HTTP calls, path allowlist, JWT forwarding, mutation confirmation, multipart upload, and base64 download. |
| `mcp_server.py` | FastMCP instance, typed tool definitions, and tool docstrings. |
| `main.py` | FastAPI health/proxy endpoints and mounted FastMCP HTTP application. |

## Extension workflow

Add a client method for repeated or complex operations, add a typed tool with a precise docstring and explicit user-token argument, update `API_TOOL_COVERAGE.md`, and add a safety test. Keep the generic allowlist synchronized with every route family that agents are allowed to access. New mutations must remain confirmation-protected.

## Local commands

```bash
cd services/kibegi-agent
. .venv/bin/activate
pip install -r requirements.txt
GO_API_BASE_URL=http://127.0.0.1:8080 uvicorn app.main:app --host 0.0.0.0 --port 8091
```

The gateway should not access PostgreSQL, Redis, or MinIO directly. It forwards user JWTs to Go and returns upstream status/payload data. Deploy it behind TLS and an authenticated ingress before exposing `/mcp`.
