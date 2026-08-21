# Kibegi Backend Documentation

This directory is the operational and architectural reference for the Go-primary Kibegi backend. It explains how the HTTP service, PostgreSQL repositories, Redis coordination, MinIO/S3 storage, provider adapters, FastAPI AI indexer, and FastMCP agent gateway work together.

## Reading order

| Guide | Audience | Purpose |
|---|---|---|
| [Architecture](architecture.md) | Engineers and reviewers | Explains process boundaries, request flow, dependency direction, and service ownership. |
| [API contract](api-contract.md) | Frontend and integration engineers | Documents routes, envelopes, status conventions, authentication, pagination, and compatibility behavior. |
| [Data model](data-model.md) | Backend engineers and operators | Describes existing PostgreSQL tables, identifiers, transactions, cache authority, and object keys. |
| [Configuration](configuration.md) | Developers and operators | Maps environment variables to runtime behavior and safe defaults. |
| [Security](security.md) | Security reviewers and operators | Covers JWT, password verification, rate limiting, CORS, service tokens, storage access, and secrets. |
| [Operations](operations.md) | Operators | Covers processes, health checks, logs, backups, Redis/DB readiness, and rollback procedures. |
| [Deployment](deployment.md) | Platform engineers | Provides VPS, Docker Compose, reverse-proxy, private-network, and service-startup guidance. |
| [Testing](testing.md) | Contributors and CI maintainers | Lists all verification commands and expected smoke-test behavior. |
| [AI indexer](ai-indexer.md) | AI and platform engineers | Describes FastAPI extraction, chunking, jobs, embeddings, callbacks, locks, and retries. |
| [Agent and MCP](agent-mcp.md) | Agent and integration engineers | Describes the FastAPI gateway, FastMCP tools, JWT forwarding, mutation confirmation, and tool coverage. |
| [Troubleshooting](troubleshooting.md) | Everyone operating the system | Provides symptom-to-diagnosis procedures for common failures. |

## Folder documentation

Every production code boundary also contains a local README. The local READMEs explain package responsibilities, dependencies, important files, and extension rules. Start at [`cmd/kibegi-api/README.md`](../cmd/kibegi-api/README.md), [`internal/apps/README.md`](../internal/apps/README.md), [`internal/platform/README.md`](../internal/platform/README.md), [`services/ai-indexer/README.md`](../services/ai-indexer/README.md), or [`services/kibegi-agent/README.md`](../services/kibegi-agent/README.md) when working inside one boundary.

## Documentation policy

Documentation must describe the current Go-primary implementation rather than historical Django internals. When an endpoint, environment variable, table query, provider, or service boundary changes, update the nearest folder README and the relevant guide in this directory in the same change. Operational instructions must never contain real credentials, production tokens, or private customer data.
