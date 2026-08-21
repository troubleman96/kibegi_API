# `internal/platform/email`

## Responsibility

This package sends SMTP email used by registration OTP, password reset, approval, and other transactional flows.

## Provider behavior

The adapter receives host, port, credentials, sender, and TLS settings from configuration. It should use bounded network timeouts, return explicit provider errors, and never claim delivery before the SMTP operation succeeds. Local development may run without SMTP; affected flows should report the provider as unavailable.

## Security

Do not log passwords, SMTP credentials, OTP values, full reset URLs, or private message bodies. Keep sender configuration in environment secrets and use a dedicated operational mailbox for production.
