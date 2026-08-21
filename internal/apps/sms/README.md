# `internal/apps/sms`

## Responsibility

The SMS package owns generic-owner SMS account detail, credit top-up, and delivery history under `/api/v1/sms/`. It preserves the existing generic content-type relationship and `sms_smsaccount`/delivery tables.

## Wallet integrity

Top-ups must validate owner type and ID, use PostgreSQL updates, record the reference, and return the authoritative balance. Sending operations in schedule, channel, and class communications must consume credits conditionally and write delivery records; this package exposes the central account view and top-up behavior.

## Provider boundary

The package stores account/provider metadata but delegates actual outbound SMS to `internal/platform/sms`. Never expose provider API keys or raw credentials in account responses. Delivery history should be scoped to the authorized owner and use bounded pagination.
