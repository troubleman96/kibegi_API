# `services/kibegi-agent/tests`

These tests protect the gateway policy rather than duplicate Go domain tests. They verify that paths outside the migrated API namespace are rejected and that mutations require explicit confirmation.

Add tests when introducing a new tool for user-token forwarding, query/body serialization, upload-size limits, download encoding, error conversion, and MCP schema registration. Integration tests should use a mock Go API or isolated test server and must never send mutations to production.

Run the suite with:

```bash
PYTHONPATH=services/kibegi-agent pytest -q services/kibegi-agent/tests
```
