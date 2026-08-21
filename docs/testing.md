# Kibegi Testing Guide

## Go checks

Run the following from the repository root before every Go commit:

```bash
GOTOOLCHAIN=local gofmt -w internal cmd
GOTOOLCHAIN=local go test ./...
GOTOOLCHAIN=local go test -race ./...
GOTOOLCHAIN=local go vet ./...
GOTOOLCHAIN=local go build -o /tmp/kibegi-api ./cmd/kibegi-api/
git diff --check
```

The unit tests cover health behavior, class handlers, schedule rendering, upload file-type and media URL behavior, cache/database/storage helpers, authentication password/JWT behavior, and middleware. Packages that require external services should expose safe unconfigured behavior so the general suite remains deterministic.

## Python checks

Compile both support services and run their tests with explicit `PYTHONPATH` values:

```bash
python3 -m compileall -q services/ai-indexer/app services/kibegi-agent/app
PYTHONPATH=services/ai-indexer pytest -q services/ai-indexer/tests
PYTHONPATH=services/kibegi-agent pytest -q services/kibegi-agent/tests
```

The indexer tests validate supported-file gating and chunk overlap. The gateway tests validate route allowlisting and mutation confirmation. Add unit tests for any new extractor, repository operation, tool, or safety control.

## Import and route checks

Import both FastAPI applications without production credentials and inspect startup routes:

```bash
PYTHONPATH=services/ai-indexer python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8090
PYTHONPATH=services/kibegi-agent python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8091
```

The indexer should start in degraded mode if PostgreSQL is absent, not crash on import. The gateway should start without storing tokens and should expose `/health`, `/v1/proxy`, and `/mcp`.

## Isolated smoke tests

Run the Go binary and support services on unused local ports with intentionally absent external credentials. Verify the following behavior:

| Check | Expected result |
|---|---|
| Go `/api/v1/health/` without database | HTTP `503` with the standard envelope. |
| Go CORS preflight | HTTP `204` with CORS headers and request ID. |
| Go protected route without JWT | HTTP `401` with the standard envelope. |
| Indexer protected route without service token | HTTP `401`. |
| Indexer indexing route without database | HTTP `503`. |
| Agent proxy with an invalid path | HTTP `400`. |
| Agent mutation without confirmation | HTTP `400` or a tool-level validation error. |
| FastMCP endpoint startup | Endpoint responds according to the configured transport. |

## Integration checks with real services

A deployment-backed test must use a protected test database, test Redis, test bucket, and non-production provider credentials. Create a test upload, verify the row and object, confirm that the Go callback reaches the indexer, inspect the processing job, confirm chunks, and test a retry after an intentional embedding-provider failure. Verify that a failed indexer does not cause the original upload response to become a failure.

For the agent, connect an MCP client, call `health`, call one authenticated read tool, call `api_request` for a detail route, and verify that a mutation is rejected without `confirm=true` and succeeds only with a valid user token and explicit confirmation.

## Documentation checks

Verify every documentation link and command path after changing directories or services. Search for deleted Django paths and stale setup commands:

```bash
grep -RInE 'manage\.py|django\.core|apps/(authentication|classes|uploads)|python manage' README.md docs cmd internal services || true
find . -type f -name '*.py' | sort
```

The only tracked Python files should be under `services/ai-indexer/` and `services/kibegi-agent/`. Documentation must refer to the Go API, FastAPI indexer, or FastMCP gateway rather than removed Django entrypoints.
