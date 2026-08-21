# Kibegi Backend Architecture

## Architectural position

Kibegi is a **Go-primary modular backend**. The public domain API is one Go process with one package per preserved business domain. Python exists only for two narrowly scoped support services: asynchronous AI document indexing and the agent/FastMCP gateway. The Go API remains the authority for authentication, business rules, durable writes, response contracts, and public route registration.

> **Design principle:** PostgreSQL is the source of truth, Redis is an accelerator and coordination system, MinIO/S3 stores binary objects, and the Python services complement rather than duplicate the Go domain layer.

## Process topology

```text
                                      +----------------------+
                                      | Frontend / API client |
                                      +----------+-----------+
                                                 |
                                                 | HTTPS
                                                 v
                                      +----------------------+
                                      | Reverse proxy / TLS   |
                                      +-----+-------------+----+
                                            |             |
                                  api.kibegi.com     agent.kibegi.com
                                            |             |
                                            v             v
                                      +-----+-----+  +----+----------------+
                                      | Go API    |  | FastAPI + FastMCP    |
                                      | :8080     |  | gateway :8091        |
                                      +--+--+--+--+  +---------+------------+
                                         |  |  |                 |
                      +------------------+  |  +-----------------+
                      |                     |                    |
                      v                     v                    v
                +-----+-----+         +-----+-----+        +-----+---------+
                | PostgreSQL|         | Redis     |        | MinIO/S3      |
                | Django DB |         | cache/lock|        | objects       |
                +-----------+         +-----------+        +---------------+
                      ^
                      |
                      | upload callback / private network
                      v
                +-----+----------------+
                | FastAPI AI indexer   |
                | :8090                |
                +----------------------+
```

## Go process boundaries

The entrypoint at `cmd/kibegi-api/main.go` loads environment configuration, opens the PostgreSQL pool, creates the Redis client, initializes MinIO/S3 and provider adapters, constructs each app package, registers routes, and wraps the multiplexer with timeout, rate limiting, CORS, recovery, access logging, and request-ID middleware.

The `internal/apps` packages own domain handlers, repositories, payload shaping, authorization decisions, and transactions for their respective namespaces. They may depend on `internal/platform` services and the authentication package, but domain packages should not import one another’s private implementation details. Cross-domain writes should use explicit repository methods or shared notification/cache primitives.

The `internal/platform` packages provide infrastructure without owning business records. The database package owns pool creation; cache owns Redis operations; storage owns MinIO/S3 operations; email and SMS own provider calls; HTTPX owns the response envelope; middleware owns shared HTTP controls.

## Request lifecycle

A request reaches the Go server through the outer middleware chain. The request-ID layer preserves a supplied `X-Request-ID` or creates one, the access logger records method/path/status/bytes/duration, the recovery layer converts panics to the standard envelope, CORS handles browser headers and preflight, the Redis rate limiter counts the client address when Redis is available, and the timeout wrapper bounds request execution.

The route handler then applies authentication where required, parses the preserved trailing-slash path, validates JSON or multipart input, calls a repository, shapes a Django-compatible envelope or download response, and invalidates relevant cache keys after mutations. Durable state is committed to PostgreSQL before the success response is returned.

## Upload and indexing flow

The Go upload handler authenticates the user, validates the multipart file and class membership, writes the object to MinIO/S3, inserts the upload row into `uploads_upload`, and returns the normal upload response. After a successful database insert it asynchronously calls the private FastAPI indexer with the upload UUID. The callback is deliberately non-blocking so indexer downtime does not make a successful file upload fail.

The indexer obtains the upload row and object key from PostgreSQL, acquires a Redis lock keyed by upload UUID, downloads the object, extracts supported formats, chunks text, writes `ai_documentchunk`, and updates `ai_aiprocessingjob`. Embeddings are optional; if the provider is unavailable, zero vectors preserve chunk position and keyword retrieval remains possible.

## Agent and MCP flow

The FastAPI/FastMCP gateway is a protocol adapter, not a second domain server. An MCP client calls typed tools or the allowlisted generic `api_request` tool. The gateway validates the path, requires explicit confirmation for non-GET operations, forwards the caller’s JWT to Go, and returns Go’s response. The gateway does not store user tokens or domain data. It can be bound to a private network or exposed through a separately authenticated HTTPS hostname.

## Dependency direction

| Layer | May depend on | Must not own |
|---|---|---|
| `cmd/kibegi-api` | All internal packages | Domain logic or database schema definitions. |
| `internal/apps/<app>` | Authentication, platform services, standard library | Other app internals without an explicit shared contract. |
| `internal/platform` | Standard library and infrastructure libraries | User-facing route decisions. |
| FastAPI indexer | PostgreSQL, Redis, MinIO/S3, extraction libraries, embedding provider | Public business API routing. |
| FastMCP gateway | HTTP client, FastMCP, Go API | Durable domain state. |

## Failure isolation

Redis failure degrades caching, rate limiting, and coordination but must not corrupt PostgreSQL state. MinIO failure prevents binary operations and should return a provider/storage error without fabricating a database success. SMTP or SMS provider failure should return a provider-specific error for the affected operation. Indexer failure is isolated from upload success and remains visible through processing-job state and indexer logs. Agent gateway failure does not affect the Go API.
