# `services/ai-indexer/tests`

These tests cover deterministic behavior that does not require PostgreSQL, Redis, MinIO, or an embedding provider. Current coverage verifies supported-file gating and overlap-preserving chunking.

When adding extractors, include small in-memory or generated-safe fixtures that do not contain customer documents. Test empty text, unsupported types, large-content limits, paragraph boundaries, overlap behavior, and extraction failures. Repository and provider integration tests should use isolated test dependencies and never production buckets or databases.

Run the suite with:

```bash
PYTHONPATH=services/ai-indexer pytest -q services/ai-indexer/tests
```
