from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from packages.persona.domain import Recipient


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class MemoryItem:
    content: str
    provenance: str
    sensitivity: str = "private"
    allowed_audiences: frozenset[str] = frozenset()
    confidence: float = 1.0
    memory_id: str = field(default_factory=lambda: f"mem_{uuid4().hex}")
    created_at: str = field(default_factory=utc_now)
    last_confirmed_at: str | None = None
    expires_at: str | None = None
    superseded_by: str | None = None
    deleted: bool = False
    revision: int = 1


@dataclass(frozen=True)
class MemoryRevision:
    memory_id: str
    revision: int
    content: str
    changed_at: str
    change_reason: str


@dataclass(frozen=True)
class MemoryProposal:
    content: str
    provenance: str
    sensitivity: str = "private"
    allowed_audiences: frozenset[str] = frozenset()
    proposal_id: str = field(default_factory=lambda: f"proposal_{uuid4().hex}")
    status: str = "pending"


class MemoryService:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self._items: dict[str, MemoryItem] = {}
        self._revisions: dict[str, list[MemoryRevision]] = {}
        self._proposals: dict[str, MemoryProposal] = {}
        self._audit_events: list[dict[str, str]] = []
        self._db: sqlite3.Connection | None = None
        if db_path is not None:
            path = Path(db_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(path)
            self._initialize_database()
            self._load_database()

    def _initialize_database(self) -> None:
        assert self._db is not None
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS memories (
                memory_id TEXT PRIMARY KEY, content TEXT NOT NULL, provenance TEXT NOT NULL,
                sensitivity TEXT NOT NULL, allowed_audiences TEXT NOT NULL, confidence REAL NOT NULL,
                created_at TEXT NOT NULL, last_confirmed_at TEXT, expires_at TEXT,
                superseded_by TEXT, deleted INTEGER NOT NULL, revision INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS memory_revisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, memory_id TEXT NOT NULL, revision INTEGER NOT NULL,
                content TEXT NOT NULL, changed_at TEXT NOT NULL, change_reason TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS memory_proposals (
                proposal_id TEXT PRIMARY KEY, content TEXT NOT NULL, provenance TEXT NOT NULL,
                sensitivity TEXT NOT NULL, allowed_audiences TEXT NOT NULL, status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS memory_audit_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT, memory_id TEXT, event_type TEXT NOT NULL,
                occurred_at TEXT NOT NULL, detail TEXT NOT NULL
            );
            """
        )
        self._db.commit()

    def _load_database(self) -> None:
        assert self._db is not None
        for row in self._db.execute("SELECT * FROM memories"):
            self._items[row[0]] = MemoryItem(row[1], row[2], row[3], frozenset(json.loads(row[4])), row[5], row[0], row[6], row[7], row[8], row[9], bool(row[10]), row[11])
        for row in self._db.execute("SELECT memory_id, revision, content, changed_at, change_reason FROM memory_revisions ORDER BY id"):
            self._revisions.setdefault(row[0], []).append(MemoryRevision(*row))
        for row in self._db.execute("SELECT * FROM memory_proposals"):
            self._proposals[row[0]] = MemoryProposal(row[1], row[2], row[3], frozenset(json.loads(row[4])), row[0], row[5])
        for row in self._db.execute("SELECT memory_id, event_type, occurred_at, detail FROM memory_audit_events ORDER BY event_id"):
            self._audit_events.append({"memory_id": row[0] or "", "event_type": row[1], "occurred_at": row[2], "detail": row[3]})

    def _audit(self, event_type: str, memory_id: str | None, detail: str) -> None:
        event = {"memory_id": memory_id or "", "event_type": event_type, "occurred_at": utc_now(), "detail": detail}
        self._audit_events.append(event)
        if self._db is not None:
            self._db.execute("INSERT INTO memory_audit_events (memory_id, event_type, occurred_at, detail) VALUES (?, ?, ?, ?)", (event["memory_id"], event_type, event["occurred_at"], detail))
            self._db.commit()

    def _persist_item(self, item: MemoryItem) -> None:
        if self._db is not None:
            self._db.execute(
                "INSERT OR REPLACE INTO memories VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (item.memory_id, item.content, item.provenance, item.sensitivity, json.dumps(sorted(item.allowed_audiences)), item.confidence, item.created_at, item.last_confirmed_at, item.expires_at, item.superseded_by, int(item.deleted), item.revision),
            )
            self._db.commit()

    @staticmethod
    def _expired(item: MemoryItem) -> bool:
        return item.expires_at is not None and datetime.fromisoformat(item.expires_at) <= datetime.now(timezone.utc)

    def create(self, item: MemoryItem) -> MemoryItem:
        self._items[item.memory_id] = item
        self._revisions[item.memory_id] = [MemoryRevision(item.memory_id, 1, item.content, utc_now(), "created")]
        self._persist_item(item)
        if self._db is not None:
            self._db.execute("INSERT INTO memory_revisions (memory_id, revision, content, changed_at, change_reason) VALUES (?, ?, ?, ?, ?)", (item.memory_id, 1, item.content, utc_now(), "created"))
            self._db.commit()
        self._audit("created", item.memory_id, item.provenance)
        return item

    def get(self, memory_id: str) -> MemoryItem | None:
        item = self._items.get(memory_id)
        return item if item and not item.deleted and item.superseded_by is None and not self._expired(item) else None

    def list(self) -> tuple[MemoryItem, ...]:
        return tuple(item for item in self._items.values() if not item.deleted and item.superseded_by is None and not self._expired(item))

    def update(self, memory_id: str, content: str, reason: str) -> MemoryItem:
        current = self._items.get(memory_id)
        if current is None or current.deleted:
            raise KeyError(memory_id)
        updated = replace(current, content=content, revision=current.revision + 1, last_confirmed_at=utc_now())
        self._items[memory_id] = updated
        self._revisions[memory_id].append(MemoryRevision(memory_id, updated.revision, content, utc_now(), reason))
        self._persist_item(updated)
        if self._db is not None:
            self._db.execute("INSERT INTO memory_revisions (memory_id, revision, content, changed_at, change_reason) VALUES (?, ?, ?, ?, ?)", (memory_id, updated.revision, content, utc_now(), reason))
            self._db.commit()
        self._audit("updated", memory_id, reason)
        return updated

    def delete(self, memory_id: str, reason: str = "user deleted") -> None:
        current = self._items.get(memory_id)
        if current is None:
            raise KeyError(memory_id)
        self._items[memory_id] = replace(current, deleted=True, revision=current.revision + 1)
        deletion_revision = MemoryRevision(memory_id, current.revision + 1, "", utc_now(), reason)
        self._revisions[memory_id].append(deletion_revision)
        self._persist_item(self._items[memory_id])
        if self._db is not None:
            self._db.execute("INSERT INTO memory_revisions (memory_id, revision, content, changed_at, change_reason) VALUES (?, ?, ?, ?, ?)", (memory_id, deletion_revision.revision, "", deletion_revision.changed_at, reason))
            self._db.commit()
        self._audit("deleted", memory_id, reason)

    def supersede(self, memory_id: str, replacement: MemoryItem, reason: str = "superseded") -> MemoryItem:
        current = self._items.get(memory_id)
        if current is None or current.deleted:
            raise KeyError(memory_id)
        self._items[memory_id] = replace(current, superseded_by=replacement.memory_id, revision=current.revision + 1)
        self._persist_item(self._items[memory_id])
        supersede_revision = MemoryRevision(memory_id, current.revision + 1, current.content, utc_now(), reason)
        self._revisions[memory_id].append(supersede_revision)
        if self._db is not None:
            self._db.execute("INSERT INTO memory_revisions (memory_id, revision, content, changed_at, change_reason) VALUES (?, ?, ?, ?, ?)", (memory_id, supersede_revision.revision, current.content, supersede_revision.changed_at, reason))
            self._db.commit()
        self.create(replacement)
        self._audit("superseded", memory_id, f"replacement={replacement.memory_id}; {reason}")
        return replacement

    def revisions(self, memory_id: str) -> tuple[MemoryRevision, ...]:
        return tuple(self._revisions.get(memory_id, ()))

    def audit_events(self) -> tuple[dict[str, str], ...]:
        return tuple(self._audit_events)

    def retrieve(self, query: str, recipient: Recipient, limit: int = 5) -> tuple[MemoryItem, ...]:
        terms = {term.lower() for term in query.split() if len(term) > 2}
        scored: list[tuple[int, MemoryItem]] = []
        for item in self.list():
            if item.sensitivity in {"private", "secret"} and recipient not in {Recipient.MASTER_PRIVATE, Recipient.SILENT_OPERATOR_NOTE}:
                continue
            if item.allowed_audiences and recipient.value not in item.allowed_audiences:
                continue
            score = sum(1 for term in terms if term in item.content.lower())
            if score:
                scored.append((score, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return tuple(item for _, item in scored[:limit])

    def propose(self, proposal: MemoryProposal) -> MemoryProposal:
        self._proposals[proposal.proposal_id] = proposal
        if self._db is not None:
            self._db.execute("INSERT OR REPLACE INTO memory_proposals VALUES (?, ?, ?, ?, ?, ?)", (proposal.proposal_id, proposal.content, proposal.provenance, proposal.sensitivity, json.dumps(sorted(proposal.allowed_audiences)), proposal.status))
            self._db.commit()
        self._audit("proposal_created", None, proposal.proposal_id)
        return proposal

    def proposals(self) -> tuple[MemoryProposal, ...]:
        return tuple(self._proposals.values())

    def approve(self, proposal_id: str) -> MemoryItem:
        proposal = self._proposals[proposal_id]
        if proposal.status != "pending":
            raise ValueError(f"proposal is already {proposal.status}")
        item = self.create(MemoryItem(content=proposal.content, provenance=proposal.provenance, sensitivity=proposal.sensitivity, allowed_audiences=proposal.allowed_audiences))
        self._proposals[proposal_id] = replace(proposal, status="approved")
        self._persist_proposal(self._proposals[proposal_id])
        self._audit("proposal_approved", item.memory_id, proposal_id)
        return item

    def reject(self, proposal_id: str) -> MemoryProposal:
        proposal = self._proposals[proposal_id]
        self._proposals[proposal_id] = replace(proposal, status="rejected")
        self._persist_proposal(self._proposals[proposal_id])
        self._audit("proposal_rejected", None, proposal_id)
        return self._proposals[proposal_id]

    def _persist_proposal(self, proposal: MemoryProposal) -> None:
        if self._db is not None:
            self._db.execute("INSERT OR REPLACE INTO memory_proposals VALUES (?, ?, ?, ?, ?, ?)", (proposal.proposal_id, proposal.content, proposal.provenance, proposal.sensitivity, json.dumps(sorted(proposal.allowed_audiences)), proposal.status))
            self._db.commit()
