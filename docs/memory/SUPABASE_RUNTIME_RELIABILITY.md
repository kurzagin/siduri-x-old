# Supabase Memory Runtime Reliability

## Purpose

This document defines how Siduri safely uses Supabase Postgres from the
threaded local orchestrator. It covers connection ownership, transaction-pooler
compatibility, bounded failure behavior, configuration, and troubleshooting.

The governing persistence decision remains
[ADR 009](../adr/009-supabase-authoritative-memory.md): Supabase is the only
authoritative persistent memory backend. This document describes the runtime
mechanics of that decision.

## Failure that motivated this design

The original implementation kept one long-lived Psycopg connection on
`SupabaseMemoryService`. `ThreadingHTTPServer` could use that connection from
multiple request threads. A chat request could consequently stall during memory
retrieval before the model call. The Next.js proxy waited for five minutes and
then displayed:

```text
I couldn’t reach the orchestrator.
Error: {"error":"Siduri orchestrator is unavailable.","detail":"TypeError: fetch failed"}
```

The orchestrator remained healthy because the failure affected one request,
not the listening process. Telemetry ended after `behavioral_memory_compiled`
and before `request_started`, locating the stall in Supabase retrieval.

Concurrent testing reproduced the database-side error:

```text
psycopg.errors.DuplicatePreparedStatement:
prepared statement "_pg3_0" already exists
```

Supabase's transaction pooler may assign transactions from one client
connection to different Postgres backend sessions. Psycopg's automatic named
prepared statements are connection-local and are incompatible with that mode
unless preparation is disabled.

## Runtime design

`SupabaseMemoryService.connect()` creates a Psycopg `ConnectionPool` instead of
sharing one connection across request threads.

```text
HTTP request thread
        |
        v
SupabaseMemoryService._borrow()
        |
        +-- borrow one checked pool connection
        +-- begin one transaction
        +-- apply transaction-local timeouts
        +-- execute the memory operation
        +-- commit/rollback
        +-- return connection to pool
```

The key invariants are:

1. A request borrows a connection; it does not own a global shared transaction.
2. Automatic prepared statements are disabled with `prepare_threshold=None`.
3. Every borrowed operation runs in one transaction, pinning it to one backend
   for the duration of the operation.
4. `statement_timeout`, `lock_timeout`, and
   `idle_in_transaction_session_timeout` are applied with transaction-local
   `set_config` calls. Supabase's transaction pooler does not reliably forward
   libpq startup `options`, so startup-only timeout configuration is insufficient.
5. Pool checkout validates the connection before use. Broken connections are
   discarded rather than remaining the process-wide memory channel.
6. TCP keepalive and `tcp_user_timeout` bound dead-peer detection below the
   frontend proxy's five-minute timeout.

Direct connection injection remains available only for deterministic unit
tests and one-shot tooling. Production startup uses the pool.

## Configuration

The defaults are listed in `.env.example` and may be overridden in the ignored
local `.env`:

```dotenv
SIDURI_SUPABASE_POOL_SIZE=5
SIDURI_SUPABASE_POOL_TIMEOUT=10
SIDURI_SUPABASE_CONNECT_TIMEOUT=8
SIDURI_SUPABASE_STATEMENT_TIMEOUT_MS=15000
SIDURI_SUPABASE_LOCK_TIMEOUT_MS=5000
```

| Variable | Meaning | Default |
| --- | --- | ---: |
| `SIDURI_SUPABASE_POOL_SIZE` | Maximum concurrent database connections | `5` |
| `SIDURI_SUPABASE_POOL_TIMEOUT` | Maximum seconds to wait for a connection | `10` |
| `SIDURI_SUPABASE_CONNECT_TIMEOUT` | Maximum seconds to establish a connection | `8` |
| `SIDURI_SUPABASE_STATEMENT_TIMEOUT_MS` | Statement limit and TCP user timeout | `15000` |
| `SIDURI_SUPABASE_LOCK_TIMEOUT_MS` | Maximum Postgres lock wait | `5000` |

The idle transaction limit is fixed at 30 seconds. Increasing these values
should be exceptional: chat should fail clearly before the frontend proxy does.

## HTTP failure behavior

Known validation errors return `400`; model-provider exhaustion returns `503`.
Any other exception from a POST operation is logged with its traceback and
returns bounded JSON:

```json
{
  "error": "Siduri could not complete this request.",
  "detail": "OperationalError"
}
```

Only the exception class is sent to the browser. Connection strings, SQL
parameters, prompts, credentials, and private memory are not included. This
prevents an exception from silently closing the orchestrator socket and
surfacing as an opaque Next.js `502`.

## Troubleshooting

### Chat spins and ends with a 502

Check both request logs:

```text
POST /chat HTTP/1.1 ...
POST /api/siduri/chat ...
```

If Next.js logs a `502` but the orchestrator never logs a completed `/chat`, the
upstream handler did not return. Inspect the Python traceback and `/telemetry`.
An event ending at `behavioral_memory_compiled` means failure occurred during
memory retrieval before model generation.

After changing pool code or environment settings, restart `./start.sh`; the
running Python process does not reload either automatically.

### `DuplicatePreparedStatement`

Confirm production construction still sets `prepare_threshold=None`. Do not
enable automatic preparation while using Supabase's transaction pooler.

### Statement timeout appears as `2min`

Do not rely on the `options` connection parameter. Verify the setting from
inside `SupabaseMemoryService._borrow()`, where it should report `15s`. The
timeout must be transaction-local to follow the transaction-pooler backend.

### Other 503 responses

`GET /obs/health` may return `503` when OBS is configured but unavailable.
`GET /evidence` may return `503` when E-Teyvat is unreachable. Those responses
are independent of Supabase memory and do not mean the orchestrator is down.

## Verification

The regression gate is:

```bash
.venv/bin/python -m unittest discover -s tests -v
npm run typecheck
npm run build
git diff --check
```

The August 8, 2026 runtime verification additionally proved:

- 32 concurrent real Supabase claim retrievals completed without failure;
- effective transaction-local limits were `15s`, `5s`, and `30s`;
- three simultaneous end-to-end `/chat` requests returned HTTP `200`;
- an injected unexpected chat exception returned HTTP `500` JSON instead of
  dropping the socket.

Live stress checks use ordinary non-teaching messages or read-only retrieval.
They must not create or approve personal memory as a side effect.
