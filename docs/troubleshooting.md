# Kibegi Troubleshooting

## Go API does not start

Check that the binary was built with `GOTOOLCHAIN=local`, that `HTTP_ADDR` is not already occupied, and that required environment variables are visible to the service account. Inspect the first startup log lines for database, Redis, MinIO, SMTP, and SMS configuration warnings. A warning about an optional provider is expected in local development; a bind error or invalid database URL is not.

## Health returns `503`

Read the JSON `checks` object. If `database` is missing or failed, verify `DATABASE_URL`, DNS, PostgreSQL availability, TLS/SSL mode, credentials, and connection limits. If Redis is failed, verify `REDIS_URL`, authentication, network policy, and pool settings. The API may still serve non-readiness-dependent paths when Redis is unavailable, but production should not treat that as healthy.

## Protected endpoint returns `401`

Confirm the client sends `Authorization: Bearer <access-token>` without extra quotes or whitespace. Check token expiry, `SECRET_KEY` consistency, issuer/audience settings if configured, and whether the request reached the intended API process. A gateway call must supply the user JWT separately from `GO_API_SERVICE_TOKEN`.

## Protected endpoint returns `403`

The token is valid but domain authorization failed. Check user membership, class ownership, role, lecturer approval, phone verification, share status, or resource ownership. Do not solve a 403 by weakening middleware; inspect the domain handler and repository query.

## Upload fails

For multipart failures, confirm the part is named `file` and the class identifier is supplied as `class_obj`. Check the 50MB limit, MinIO configuration, bucket policy, object endpoint, and class membership. If the row insert fails after an object write, the handler should remove the object; inspect storage and database logs using the request ID.

## Upload succeeds but AI indexing is missing

Check `AI_INDEXER_URL` and `AI_INDEXER_TOKEN` in the Go process environment, confirm the indexer is reachable on the private network, and inspect the indexer log for the upload UUID. Query `GET /v1/index/jobs/{upload_id}`. If no job exists, run the batch endpoint or polling runner. If the job is failed, verify the object key, supported extension, file size, extractor dependencies, and embedding provider. A successful upload should not be rolled back because indexing is asynchronous.

## Redis errors or duplicate jobs

Verify Redis connectivity and the configured database number. The indexer lock key uses the upload UUID. Without Redis, the indexer can still operate but concurrent duplicate processing is less protected. Restore Redis before enabling multiple worker instances or high-volume retries.

## FastMCP client cannot connect

Confirm the gateway process is listening, the reverse proxy routes `/mcp` without stripping the expected path, TLS is valid, and the configured FastMCP transport matches the client. Check `MCP_ALLOWED_ORIGINS`, ingress authentication, and whether the client follows the endpoint redirect from `/mcp` to `/mcp/` when applicable.

## FastMCP tool returns `400`

A path may be outside the allowlist, a mutation may be missing `confirm=true`, a file upload may exceed 50MB, or the method/body may not match the Go route. Use the typed tool when available and consult `API_TOOL_COVERAGE.md` before using `api_request`.

## Provider failures

SMTP, SMS, MinIO, and embedding errors should be isolated to the affected operation. Check provider base URL, credentials, sender IDs, TLS, quotas, and response status. Do not expose raw provider payloads to clients or logs if they contain secrets or personal data.

## Rollback

Record the current commit and service versions before rollback. Restore the previous Go artifact or Git commit, leave PostgreSQL and object storage unchanged, verify health, and run read-only smoke tests. The pre-cleanup historical code is available at `pre-go-primary-cleanup-6148d29`; restoring it requires restoring the archive or checking out the tag in a separate worktree rather than deleting the current Go-primary branch.
