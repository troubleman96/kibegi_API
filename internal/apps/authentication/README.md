# `internal/apps/authentication`

## Responsibility

The authentication package owns user identity at the HTTP boundary. It implements login, registration, email OTP verification/resend, password reset, JWT refresh/logout, password changes, profile read/update, profile-image upload/removal, Google token exchange, lecturer approval, and phone OTP send/verify.

## Internal structure

`repository.go` maps existing `authentication_user`, OTP, and profile fields. `jwt.go` creates and validates Django SimpleJWT-compatible claims. `password.go` verifies PBKDF2-SHA256 hashes. `otp.go` handles short-lived OTP generation and Redis state. `middleware.go` exposes `RequireAuth` and request user context. `handlers.go` contains primary flows; `extras.go` contains Google, phone, lecturer, and profile-image parity handlers.

## Security and dependencies

The package receives the shared token service, Redis client, object storage, SMTP mailer, and PostgreSQL repository from the composition root. Passwords and tokens must never be logged. Profile cache entries are invalidated after profile writes. Profile-image operations validate size and content type before writing to MinIO/S3 and update the existing profile-image field only after storage succeeds.

## Routes

The app owns `/api/v1/auth/` plus root `/register/` and `/login/` compatibility shortcuts. Route aliases preserve both password-reset confirmation spellings used by existing clients. All protected profile and administrative flows enforce token identity and relevant user role/approval checks.
