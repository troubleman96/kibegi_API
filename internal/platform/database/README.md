# `internal/platform/database`

## Responsibility

This package opens the shared PostgreSQL connection pool using the pgx driver through `database/sql` and applies configurable open/idle bounds and connection lifetimes.

## Pool rules

The pool is created once by the composition root and passed to repositories. Repositories must reuse it rather than opening per-request connections. Tune pool bounds against PostgreSQL capacity and the number of Go service replicas. Use context-aware queries so request timeouts cancel database work.

## Schema policy

The database package performs connectivity and pool setup only. It does not run migrations, create tables, rename columns, or delete data. The Go service uses the existing Kibegi schema as an external contract.
