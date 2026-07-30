# ADR 003: PostgreSQL portability

## Context

Local tests must run without a database daemon, while deployment may require PostgreSQL.

## Decision

Keep service boundaries repository-oriented. SQLite is the local durable backend; PostgreSQL migrations and adapters remain the deployment portability path.

## Consequences

Offline tests remain reproducible. Production deployment must verify migration parity and backup/restore procedures.
