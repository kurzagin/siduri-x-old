"""Optional PostgreSQL persistence adapter.

The default development path uses SQLite so the test suite needs no service. Install
the ``postgres`` extra to use this adapter with the SQL in migrations/002_memory.sql.
"""
from __future__ import annotations

import json
from typing import Any

from packages.memory.service import MemoryItem


class PostgresMemoryRepository:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    @classmethod
    def connect(cls, dsn: str) -> "PostgresMemoryRepository":
        try:
            import psycopg
        except ImportError as error:  # pragma: no cover - exercised only when optional extra is absent
            raise RuntimeError("Install siduri[postgres] to use PostgreSQL persistence") from error
        return cls(psycopg.connect(dsn))

    def save(self, item: MemoryItem) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO memories (memory_id, content, provenance, sensitivity, allowed_audiences,
                    confidence, created_at, last_confirmed_at, expires_at, superseded_by, deleted, revision)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (memory_id) DO UPDATE SET content=EXCLUDED.content,
                    last_confirmed_at=EXCLUDED.last_confirmed_at, expires_at=EXCLUDED.expires_at,
                    superseded_by=EXCLUDED.superseded_by, deleted=EXCLUDED.deleted, revision=EXCLUDED.revision
                """,
                (item.memory_id, item.content, item.provenance, item.sensitivity, json.dumps(sorted(item.allowed_audiences)), item.confidence, item.created_at, item.last_confirmed_at, item.expires_at, item.superseded_by, item.deleted, item.revision),
            )
        self.connection.commit()

    def audit(self, event_id: str, memory_id: str | None, event_type: str, occurred_at: str, detail: dict[str, str]) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute("INSERT INTO memory_audit_events (event_id, memory_id, event_type, occurred_at, detail) VALUES (%s, %s, %s, %s, %s::jsonb)", (event_id, memory_id, event_type, occurred_at, json.dumps(detail)))
        self.connection.commit()
