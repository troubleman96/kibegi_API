# `internal`

This directory contains private Go implementation packages that are not intended for external import. It is split into `apps/` for domain behavior, `platform/` for shared infrastructure, and `config/` for environment parsing.

The composition root under `cmd/` assembles these packages. Domain packages should depend on explicit platform interfaces and preserve the existing API/database contracts. Platform packages should remain domain-neutral. Changes to private packages still require route, data-integrity, security, and documentation review because they affect the public backend.
