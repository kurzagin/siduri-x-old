"""Authoritative single-user Supabase Postgres persistence for Siduri memory."""
from __future__ import annotations

from datetime import datetime
from contextlib import contextmanager
import json
import os
import re
from typing import Any, Iterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from packages.memory.service import (
    BehaviorDef, BehavioralDirective, MemoryItem, MemoryProposal, MemoryRevision,
    MemoryService, Scope, SourceEvent, VersionedClaim, utc_now,
)


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if isinstance(value, datetime) else str(value)


def _json(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def normalize_supabase_dsn(dsn: str) -> str:
    """Remove client-specific URL flags and require encrypted Postgres transport."""
    parsed = urlsplit(dsn)
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key != "pgbouncer"]
    if not any(key == "sslmode" for key, _value in query):
        query.append(("sslmode", "require"))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


class SupabaseMemoryService(MemoryService):
    """Complete memory service backed exclusively by one Supabase database."""

    def __init__(self, connection: Any = None, *, pool: Any = None) -> None:
        super().__init__()
        if (connection is None) == (pool is None):
            raise ValueError("provide exactly one Postgres connection or connection pool")
        self.connection = connection
        self.pool = pool
        self.statement_timeout_ms = int(os.getenv("SIDURI_SUPABASE_STATEMENT_TIMEOUT_MS", "15000"))
        self.lock_timeout_ms = int(os.getenv("SIDURI_SUPABASE_LOCK_TIMEOUT_MS", "5000"))
        self._load_postgres()

    @classmethod
    def connect(cls, dsn: str) -> "SupabaseMemoryService":
        try:
            from psycopg_pool import ConnectionPool
        except ImportError as error:  # pragma: no cover
            raise RuntimeError("Install Siduri's Python dependencies to use Supabase memory") from error
        connect_timeout = int(os.getenv("SIDURI_SUPABASE_CONNECT_TIMEOUT", "8"))
        statement_timeout_ms = int(os.getenv("SIDURI_SUPABASE_STATEMENT_TIMEOUT_MS", "15000"))
        lock_timeout_ms = int(os.getenv("SIDURI_SUPABASE_LOCK_TIMEOUT_MS", "5000"))
        pool_timeout = float(os.getenv("SIDURI_SUPABASE_POOL_TIMEOUT", "10"))
        pool = ConnectionPool(
            conninfo=normalize_supabase_dsn(dsn),
            min_size=1,
            max_size=int(os.getenv("SIDURI_SUPABASE_POOL_SIZE", "5")),
            timeout=pool_timeout,
            kwargs={
                "autocommit": True,
                "connect_timeout": connect_timeout,
                # Supabase's transaction pooler can move successive operations to
                # different server sessions. Named prepared statements therefore
                # collide or disappear unless Psycopg preparation is disabled.
                "prepare_threshold": None,
                "keepalives": 1,
                "keepalives_idle": 10,
                "keepalives_interval": 5,
                "keepalives_count": 2,
                "tcp_user_timeout": statement_timeout_ms,
                "options": (
                    f"-c statement_timeout={statement_timeout_ms} "
                    f"-c lock_timeout={lock_timeout_ms} "
                    "-c idle_in_transaction_session_timeout=30000"
                ),
            },
            check=ConnectionPool.check_connection,
            open=True,
        )
        pool.wait(timeout=connect_timeout + pool_timeout)
        return cls(pool=pool)

    def close(self) -> None:
        if self.pool is not None:
            self.pool.close()
            self.pool = None
        elif self.connection is not None:
            self.connection.close()
            self.connection = None

    @contextmanager
    def _borrow(self) -> Iterator[Any]:
        """Borrow an isolated connection for one operation.

        Production uses the pool. A directly supplied connection remains available
        for deterministic unit tests and one-shot tooling.
        """
        if self.pool is not None:
            with self.pool.connection() as connection:
                # SET LOCAL and the operation must share one transaction because
                # Supabase's transaction pooler may choose a different backend for
                # every transaction. Startup options are not reliably forwarded.
                with connection.transaction():
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT set_config('statement_timeout', %s, true), "
                            "set_config('lock_timeout', %s, true), "
                            "set_config('idle_in_transaction_session_timeout', '30000', true)",
                            (str(self.statement_timeout_ms), str(self.lock_timeout_ms)),
                        )
                    yield connection
            return
        if self.connection is None:
            raise RuntimeError("Supabase memory service is closed")
        yield self.connection

    def _execute(self, statement: str, params: tuple[Any, ...]) -> None:
        with self._borrow() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, params)
            if self.pool is None:
                connection.commit()

    def _load_postgres(self) -> None:
        with self._borrow() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT memory_id, content, provenance, sensitivity, allowed_audiences, confidence, created_at, last_confirmed_at, expires_at, superseded_by, deleted, revision FROM memories")
            for row in cursor.fetchall():
                self._items[row[0]] = MemoryItem(row[1], row[2], row[3], frozenset(_json(row[4])), row[5], row[0], _iso(row[6]) or "", _iso(row[7]), _iso(row[8]), row[9], row[10], row[11])
            cursor.execute("SELECT memory_id, revision, content, changed_at, change_reason FROM memory_revisions ORDER BY changed_at, revision")
            for row in cursor.fetchall():
                self._revisions.setdefault(row[0], []).append(MemoryRevision(row[0], row[1], row[2], _iso(row[3]) or "", row[4]))
            cursor.execute("SELECT p.proposal_id, p.content, p.provenance, p.sensitivity, p.allowed_audiences, p.status, c.subject, c.predicate, c.value, c.claim_type, c.source_event_id FROM memory_proposals p LEFT JOIN memory_proposal_claims c ON c.proposal_id = p.proposal_id")
            for row in cursor.fetchall():
                self._proposals[row[0]] = MemoryProposal(row[1], row[2], row[3], frozenset(_json(row[4])), row[0], row[5], row[6] or "primary_user", row[7] or "note", row[8], row[9] or "semantic", row[10])
            cursor.execute("SELECT event_id, source_type, occurred_at, payload, schema_version FROM source_events")
            for row in cursor.fetchall():
                self._source_events[row[0]] = SourceEvent(row[0], row[1], _iso(row[2]) or "", _json(row[3]), row[4])
            cursor.execute("SELECT claim_id, subject, predicate, value, claim_type, source_event_id, provenance, authority, status, sensitivity, allowed_audiences, user_confirmation, confidence, asserted_at, valid_from, valid_until, supersedes, replaces, schema_version FROM versioned_claims")
            for row in cursor.fetchall():
                self._claims[row[0]] = VersionedClaim(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9], tuple(_json(row[10])), row[11], row[12], _iso(row[13]) or "", _iso(row[14]), _iso(row[15]), row[16], row[17], row[18])
            cursor.execute("SELECT directive_id, memory_class, domain, subject, predicate, value, activation, scope, behavior, status, source_type, source_event_id, confirmed_by, created_at, valid_from, valid_until, supersedes_id, sensitivity, confidence FROM behavioral_directives")
            for row in cursor.fetchall():
                scope_data, behavior_data = _json(row[7]), _json(row[8])
                self._behavioral_directives[row[0]] = BehavioralDirective(
                    row[0], row[1], row[2], row[3], row[4], row[5], row[6],
                    Scope(tuple(scope_data.get("recipient_ids", [])), tuple(scope_data.get("audiences", [])), tuple(scope_data.get("session_modes", []))),
                    BehaviorDef(behavior_data.get("instruction", ""), behavior_data.get("frequency", "occasional"), tuple(behavior_data.get("preferred_positions", []))),
                    row[9], row[10], row[11], row[12], _iso(row[13]) or "", _iso(row[14]), _iso(row[15]), row[16], row[17], row[18],
                )
            cursor.execute("SELECT memory_id, event_type, occurred_at, detail FROM memory_audit_events ORDER BY occurred_at")
            for row in cursor.fetchall():
                detail = _json(row[3])
                self._audit_events.append({"memory_id": row[0] or "", "event_type": row[1], "occurred_at": _iso(row[2]) or "", "detail": detail.get("detail", "") if isinstance(detail, dict) else str(detail)})

    def reset(self) -> None:
        super().reset()
        with self._borrow() as connection:
            with connection.cursor() as cursor:
                for table in ("memory_proposal_claims", "memory_revisions", "memory_audit_events", "behavioral_directives", "versioned_claims", "memory_proposals", "memories", "source_events"):
                    cursor.execute(f"DELETE FROM {table}")
            if self.pool is None:
                connection.commit()

    def _persist_item(self, item: MemoryItem) -> None:
        self._execute(
            """INSERT INTO memories (memory_id, content, provenance, sensitivity, allowed_audiences, confidence, created_at, last_confirmed_at, expires_at, superseded_by, deleted, revision)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (memory_id) DO UPDATE SET content=EXCLUDED.content, provenance=EXCLUDED.provenance, sensitivity=EXCLUDED.sensitivity, allowed_audiences=EXCLUDED.allowed_audiences, confidence=EXCLUDED.confidence, last_confirmed_at=EXCLUDED.last_confirmed_at, expires_at=EXCLUDED.expires_at, superseded_by=EXCLUDED.superseded_by, deleted=EXCLUDED.deleted, revision=EXCLUDED.revision""",
            (item.memory_id, item.content, item.provenance, item.sensitivity, json.dumps(sorted(item.allowed_audiences)), item.confidence, item.created_at, item.last_confirmed_at, item.expires_at, item.superseded_by, item.deleted, item.revision),
        )

    def _persist_revision(self, revision: MemoryRevision) -> None:
        self._execute(
            """INSERT INTO memory_revisions (memory_id, revision, content, changed_at, change_reason) VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (memory_id, revision) DO UPDATE SET content=EXCLUDED.content, changed_at=EXCLUDED.changed_at, change_reason=EXCLUDED.change_reason""",
            (revision.memory_id, revision.revision, revision.content, revision.changed_at, revision.change_reason),
        )

    def _persist_proposal(self, proposal: MemoryProposal) -> None:
        self._execute(
            """INSERT INTO memory_proposals (proposal_id, content, provenance, sensitivity, allowed_audiences, status) VALUES (%s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (proposal_id) DO UPDATE SET content=EXCLUDED.content, provenance=EXCLUDED.provenance, sensitivity=EXCLUDED.sensitivity, allowed_audiences=EXCLUDED.allowed_audiences, status=EXCLUDED.status""",
            (proposal.proposal_id, proposal.content, proposal.provenance, proposal.sensitivity, json.dumps(sorted(proposal.allowed_audiences)), proposal.status),
        )
        self._execute(
            """INSERT INTO memory_proposal_claims (proposal_id, subject, predicate, value, claim_type, source_event_id) VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (proposal_id) DO UPDATE SET subject=EXCLUDED.subject, predicate=EXCLUDED.predicate, value=EXCLUDED.value, claim_type=EXCLUDED.claim_type, source_event_id=EXCLUDED.source_event_id""",
            (proposal.proposal_id, proposal.subject, proposal.predicate, proposal.value, proposal.claim_type, proposal.source_event_id),
        )

    def add_source_event(self, event: SourceEvent) -> SourceEvent:
        result = super().add_source_event(event)
        self._execute(
            """INSERT INTO source_events (event_id, source_type, occurred_at, payload, schema_version) VALUES (%s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (event_id) DO UPDATE SET source_type=EXCLUDED.source_type, occurred_at=EXCLUDED.occurred_at, payload=EXCLUDED.payload, schema_version=EXCLUDED.schema_version""",
            (event.event_id, event.source_type, event.occurred_at, json.dumps(event.payload), event.schema_version),
        )
        return result

    def _persist_claim(self, claim: VersionedClaim) -> None:
        self._execute(
            """INSERT INTO versioned_claims (claim_id, subject, predicate, value, claim_type, source_event_id, provenance, authority, status, sensitivity, allowed_audiences, user_confirmation, confidence, asserted_at, valid_from, valid_until, supersedes, replaces, schema_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (claim_id) DO UPDATE SET subject=EXCLUDED.subject, predicate=EXCLUDED.predicate, value=EXCLUDED.value, claim_type=EXCLUDED.claim_type, provenance=EXCLUDED.provenance, authority=EXCLUDED.authority, status=EXCLUDED.status, sensitivity=EXCLUDED.sensitivity, allowed_audiences=EXCLUDED.allowed_audiences, user_confirmation=EXCLUDED.user_confirmation, confidence=EXCLUDED.confidence, valid_from=EXCLUDED.valid_from, valid_until=EXCLUDED.valid_until, supersedes=EXCLUDED.supersedes, replaces=EXCLUDED.replaces, schema_version=EXCLUDED.schema_version""",
            (claim.claim_id, claim.subject, claim.predicate, claim.value, claim.claim_type, claim.source_event_id, claim.provenance, claim.authority, claim.status, claim.sensitivity, json.dumps(list(claim.allowed_audiences)), claim.user_confirmation, claim.confidence, claim.asserted_at, claim.valid_from, claim.valid_until, claim.supersedes, claim.replaces, claim.schema_version),
        )

    def add_behavioral_directive(self, directive: BehavioralDirective) -> BehavioralDirective:
        result = super().add_behavioral_directive(directive)
        self._execute(
            """INSERT INTO behavioral_directives (directive_id, memory_class, domain, subject, predicate, value, activation, scope, behavior, status, source_type, source_event_id, confirmed_by, created_at, valid_from, valid_until, supersedes_id, sensitivity, confidence)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (directive_id) DO UPDATE SET memory_class=EXCLUDED.memory_class, domain=EXCLUDED.domain, subject=EXCLUDED.subject, predicate=EXCLUDED.predicate, value=EXCLUDED.value, activation=EXCLUDED.activation, scope=EXCLUDED.scope, behavior=EXCLUDED.behavior, status=EXCLUDED.status, confirmed_by=EXCLUDED.confirmed_by, valid_from=EXCLUDED.valid_from, valid_until=EXCLUDED.valid_until, supersedes_id=EXCLUDED.supersedes_id, sensitivity=EXCLUDED.sensitivity, confidence=EXCLUDED.confidence""",
            (directive.directive_id, directive.memory_class, directive.domain, directive.subject, directive.predicate, directive.value, directive.activation, json.dumps(directive.scope.to_dict()), json.dumps(directive.behavior.to_dict()), directive.status, directive.source_type, directive.source_event_id, directive.confirmed_by, directive.created_at, directive.valid_from, directive.valid_until, directive.supersedes_id, directive.sensitivity, directive.confidence),
        )
        return result

    def _audit(self, event_type: str, memory_id: str | None, detail: str) -> None:
        event = {"memory_id": memory_id or "", "event_type": event_type, "occurred_at": utc_now(), "detail": detail}
        self._audit_events.append(event)
        self._persist_audit_event(f"audit_{uuid4().hex}", event)

    def _persist_audit_event(self, event_id: str, event: dict[str, str]) -> None:
        self._persist_audit_events(((event_id, event),))

    def _persist_audit_events(self, events: tuple[tuple[str, dict[str, str]], ...]) -> None:
        statement = """INSERT INTO memory_audit_events (event_id, memory_id, event_type, occurred_at, detail)
        VALUES (%s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (event_id) DO UPDATE SET memory_id=EXCLUDED.memory_id,
        event_type=EXCLUDED.event_type, occurred_at=EXCLUDED.occurred_at, detail=EXCLUDED.detail"""
        params = [
            (event_id, event.get("memory_id") or None, event["event_type"], event["occurred_at"], json.dumps({"detail": event.get("detail", "")}))
            for event_id, event in events
        ]
        with self._borrow() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(statement, params)
            if self.pool is None:
                connection.commit()

    def _fts_claim_scores(self, terms: set[str], limit: int) -> dict[str, float]:
        safe_terms = [term for term in sorted(terms) if re.fullmatch(r"[a-z0-9]+", term)]
        if not safe_terms:
            return {}
        query = " | ".join(f"{term}:*" for term in safe_terms)
        with self._borrow() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT claim_id, ts_rank(search_document, to_tsquery('simple', %s)) FROM versioned_claims WHERE search_document @@ to_tsquery('simple', %s) ORDER BY 2 DESC LIMIT %s",
                    (query, query, limit),
                )
                return {row[0]: float(row[1]) for row in cursor.fetchall()}


PostgresMemoryRepository = SupabaseMemoryService
