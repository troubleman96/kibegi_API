# `internal/platform/sms`

## Responsibility

This package adapts the configured SendAfrica provider for outbound SMS, balance checks, and message formatting. Domain packages such as schedule, channel, class communications, and SMS accounts use it without depending on provider-specific HTTP details.

## Provider behavior

The adapter uses bounded HTTP timeouts, configured base URL/API key/sender ID, and normalized phone/message fields. It returns explicit provider or configuration errors. Domain code must record durable delivery state and consume credits only after the provider result meets the documented success condition.

## Compatibility and security

Legacy provider compatibility belongs in this adapter, not in handlers. Redact API keys, authorization headers, full phone lists, and provider response bodies from logs. Do not expose provider credentials through account or delivery-history payloads.
