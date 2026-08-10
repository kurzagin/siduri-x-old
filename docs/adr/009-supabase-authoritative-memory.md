# ADR 009: Supabase as Authoritative Memory

## Status

Accepted

## Context

Siduri's current development data is deliberately approved for her to know.
Designing the primary memory backend around hypothetical future local secrets
adds complexity without improving the present product. SQLite also limits
remote durability, synchronization, and future semantic retrieval. Siduri is a
single-user application, so multi-user ownership is not a product requirement.

## Decision

Supabase Postgres is Siduri's only authoritative persistent memory database.
The orchestrator requires a Supabase database connection at startup. It does
not dual-write to SQLite and does not silently fall back to local persistence.

Memory tables enable Row-Level Security without policies for Supabase client
roles. The browser has no database credentials and cannot use the Data API for
memory. Only the trusted loopback orchestrator connects through the database
URL. Existing concepts remain separate and versioned:

- pending and reviewed memory proposals;
- factual/queryable versioned claims;
- behavioral/runtime directives compiled into Active Self;
- source events, revisions, supersession, deletion, and audit events.

Postgres generated full-text search supports structured and lexical retrieval.
The claim identity and retrieval boundary allow a pgvector column and hybrid
ranking to be added after an embedding model and dimensions are selected;
embeddings are not required for this migration.

The threaded orchestrator uses a bounded Psycopg connection pool. Each memory
operation borrows a checked connection and runs in one transaction with local
statement and lock limits. Psycopg automatic prepared statements are disabled
because Supabase's transaction pooler may route transactions to different
backend sessions. Unexpected request failures return sanitized JSON and are
logged server-side instead of dropping the proxy connection.

Credentials, API keys, and machine secrets remain environment configuration,
not memory records. A future local-only memory class requires a separate ADR
and must not distort this schema prematurely.

## Consequences

- Durable operation requires Supabase configuration and network availability.
- Unit tests use an explicit in-memory service; that service is not a product
  persistence fallback.
- The old SQLite database is only an optional one-time import source.
- Supabase Auth is intentionally omitted until Siduri has another user or a
  direct authenticated client use case.
- Pool sizing and timeout values are operational configuration; changes require
  an orchestrator restart.
- Transaction-pooler compatibility is a persistence invariant, not an optional
  performance optimization.

Runtime details and troubleshooting are maintained in
[`docs/memory/SUPABASE_RUNTIME_RELIABILITY.md`](../memory/SUPABASE_RUNTIME_RELIABILITY.md).
