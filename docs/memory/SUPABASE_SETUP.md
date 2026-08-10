# Supabase Memory Setup

Siduri requires Supabase Postgres for persistent memory. There is no SQLite
runtime fallback.

## 1. Create the project

Create one Supabase project for Siduri. Supabase Auth is not required because
this Siduri instance is single-user and the browser never connects to memory
directly.

## 2. Apply the schema

After configuring the connection value described below, apply and
verify the schema directly:

```bash
.venv/bin/python scripts/setup_supabase_memory.py
```

Alternatively, run [`migrations/002_memory.sql`](../../migrations/002_memory.sql)
through the Supabase SQL editor or your normal migration pipeline. It creates
the proposal, claim, directive, revision, source-event, and audit tables,
together with full-text indexes. RLS is enabled without client policies, so
Supabase's browser-facing API roles cannot read or write Siduri memory.

Do not enable pgvector merely to complete setup. The schema supports structured
and full-text retrieval now; vector dimensions should be selected together with
an embedding model later.

## 3. Configure the orchestrator

Copy the Supabase setting from `.env.example` into the ignored `.env`:

```dotenv
SIDURI_SUPABASE_DATABASE_URL=postgresql://...
SIDURI_SUPABASE_POOL_SIZE=5
SIDURI_SUPABASE_POOL_TIMEOUT=10
SIDURI_SUPABASE_CONNECT_TIMEOUT=8
SIDURI_SUPABASE_STATEMENT_TIMEOUT_MS=15000
SIDURI_SUPABASE_LOCK_TIMEOUT_MS=5000
```

Use Supabase's pooled Postgres connection string with TLS. The database password
is infrastructure configuration and must never become a Siduri memory record or
be committed to Git.

Siduri uses a thread-safe Psycopg connection pool. Client-side prepared
statements are disabled because Supabase's transaction pooler can assign each
transaction to a different backend session. Every borrowed connection runs the
operation in one transaction with local statement and lock timeouts, preventing
a stalled memory query from holding `/chat` indefinitely.

See
[`SUPABASE_RUNTIME_RELIABILITY.md`](SUPABASE_RUNTIME_RELIABILITY.md) for the
runtime invariants, failure response contract, and troubleshooting procedure.

Install the Python environment:

```bash
python -m venv .venv
.venv/bin/pip install -e '.[platforms]'
```

## 4. Optionally import the current memory

Inspect the former SQLite dataset without writing anything:

```bash
.venv/bin/python scripts/migrate_sqlite_memory_to_supabase.py --dry-run
```

Import it once after verifying the target has no memory rows:

```bash
.venv/bin/python scripts/migrate_sqlite_memory_to_supabase.py
```

The importer reloads the Supabase service and compares item, revision,
proposal, source-event, claim, directive, and audit counts. Use `--allow-merge`
only when an intentional idempotent merge into existing data is required.

## 5. Verify runtime behavior

Start Siduri with `./start.sh`, open a fresh chat, and verify:

1. `GET /ready` reports `memory.provider_id = supabase-postgres` and
   `memory.persistent = true`.
2. Existing approved identity and relationship behavior survives a restart.
3. A new proposal appears in Supabase before approval.
4. Approval creates a confirmed claim while preserving the reviewed proposal.
5. A new conversation compiles confirmed directives into Active Self without
   relying on prior chat history.
