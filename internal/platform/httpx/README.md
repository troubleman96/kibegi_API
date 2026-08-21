# `internal/platform/httpx`

## Responsibility

This package writes the stable Kibegi JSON envelope with `success`, `message`, `data`, and `errors` fields. It also provides helpers for JSON responses and consistent error payloads.

## Contract rules

`data` and `errors` remain flexible because endpoints return objects, arrays, validation maps, or null. Use the HTTP status code to communicate transport/domain outcome and the envelope message for client-readable context. Streaming file downloads are the intentional exception and should set content type/disposition directly.

Keep envelope changes backward compatible. Add fields only when clients can ignore them, and update `docs/api-contract.md` when status or payload behavior changes.
