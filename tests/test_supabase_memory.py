from pathlib import Path
import unittest

from packages.memory.postgres import SupabaseMemoryService, normalize_supabase_dsn
from packages.memory.service import MemoryProposal, SourceEvent, utc_now


class FakeCursor:
    def __init__(self, connection: "FakeConnection") -> None:
        self.connection = connection

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, query: str, params: tuple[object, ...] = ()) -> None:
        self.connection.queries.append((query, params))

    def executemany(self, query: str, params: list[tuple[object, ...]]) -> None:
        self.connection.queries.extend((query, item) for item in params)

    def fetchall(self) -> list[tuple[object, ...]]:
        return []


class FakeConnection:
    def __init__(self) -> None:
        self.queries: list[tuple[str, tuple[object, ...]]] = []
        self.commits = 0
        self.closed = False

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def commit(self) -> None:
        self.commits += 1

    def close(self) -> None:
        self.closed = True


class SupabaseMemoryTests(unittest.TestCase):
    def test_supabase_dsn_removes_orm_pooler_flag_and_requires_tls(self) -> None:
        normalized = normalize_supabase_dsn("postgresql://user:pass@example.supabase.com/db?pgbouncer=true")
        self.assertNotIn("pgbouncer", normalized)
        self.assertIn("sslmode=require", normalized)

    def test_schema_is_single_user_backend_only_and_vector_ready(self) -> None:
        schema = Path("migrations/002_memory.sql").read_text(encoding="utf-8")
        tables = (
            "memories", "memory_revisions", "memory_proposals", "memory_audit_events",
            "source_events", "memory_proposal_claims", "versioned_claims", "behavioral_directives",
        )
        for table in tables:
            with self.subTest(table=table):
                self.assertIn(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY", schema)
        self.assertNotIn("owner_id", schema)
        self.assertNotIn("CREATE POLICY", schema)
        self.assertNotIn("auth.users", schema)
        self.assertIn("search_document TSVECTOR GENERATED ALWAYS", schema)
        self.assertNotIn("CREATE EXTENSION IF NOT EXISTS vector", schema.replace("-- CREATE EXTENSION IF NOT EXISTS vector", ""))

    def test_postgres_service_persists_the_approval_flow(self) -> None:
        connection = FakeConnection()
        memory = SupabaseMemoryService(connection)
        connection.queries.clear()

        event = memory.add_source_event(SourceEvent("evt_owner", "test", utc_now(), {"safe": True}))
        proposal = memory.propose(MemoryProposal(
            "The owner likes records.", "test", subject="primary_user", predicate="preference",
            value="records", source_event_id=event.event_id,
        ))
        memory.approve(proposal.proposal_id)

        mutations = [
            (query, params) for query, params in connection.queries
            if query.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        ]
        self.assertTrue(mutations)
        self.assertTrue(any("versioned_claims" in query for query, _params in mutations))
        self.assertTrue(any("memory_proposals" in query for query, _params in mutations))


if __name__ == "__main__":
    unittest.main()
