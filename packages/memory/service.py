from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from packages.persona.domain import Recipient


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

ClaimType = Literal["semantic", "preference", "episodic", "relationship"]
AuthorityLevel = Literal["user_explicit", "user_correction", "import", "repeated_dialogue", "inference", "observation"]
ClaimStatus = Literal["pending", "confirmed", "rejected", "session_only", "superseded", "revoked"]
UserConfirmation = Literal["explicit", "implied", "none"]
MemoryClass = Literal["identity", "relationship", "behavioral", "semantic", "episodic"]
ActivationState = Literal["always", "always_when_scope_matches", "retrieval_only", "session_only", "disabled"]
SINGLE_VALUE_PREDICATES = frozenset({
    "name",
    "uid",
    "server",
    "account_name",
    "main_character",
    "preferred_address",
    "relationship_to_siduri",
})

@dataclass(frozen=True)
class SourceEvent:
    event_id: str
    source_type: str
    occurred_at: str
    payload: dict[str, Any]
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class VersionedClaim:
    claim_id: str
    subject: str
    predicate: str
    value: str
    claim_type: ClaimType
    source_event_id: str
    provenance: str
    authority: AuthorityLevel
    status: ClaimStatus
    sensitivity: str
    allowed_audiences: tuple[str, ...]
    user_confirmation: UserConfirmation
    confidence: float = 1.0
    asserted_at: str = field(default_factory=utc_now)
    valid_from: str | None = None
    valid_until: str | None = None
    supersedes: str | None = None
    replaces: str | None = None
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["allowed_audiences"] = list(self.allowed_audiences)
        return result


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
    subject: str = "primary_user"
    predicate: str = "note"
    value: str | None = None
    claim_type: ClaimType = "semantic"
    source_event_id: str | None = None
@dataclass(frozen=True)
class Scope:
    recipient_ids: tuple[str, ...]
    audiences: tuple[str, ...]
    session_modes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class BehaviorDef:
    instruction: str
    frequency: str
    preferred_positions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class BehavioralDirective:
    directive_id: str
    memory_class: MemoryClass
    domain: str
    subject: str
    predicate: str
    value: str
    activation: ActivationState
    scope: Scope
    behavior: BehaviorDef
    status: ClaimStatus
    source_type: str
    source_event_id: str
    confirmed_by: str
    created_at: str = field(default_factory=utc_now)
    valid_from: str | None = None
    valid_until: str | None = None
    supersedes_id: str | None = None
    sensitivity: str = "private"
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["scope"] = self.scope.to_dict()
        result["behavior"] = self.behavior.to_dict()
        return result


class MemoryService:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self._items: dict[str, MemoryItem] = {}
        self._revisions: dict[str, list[MemoryRevision]] = {}
        self._proposals: dict[str, MemoryProposal] = {}
        self._source_events: dict[str, SourceEvent] = {}
        self._claims: dict[str, VersionedClaim] = {}
        self._behavioral_directives: dict[str, BehavioralDirective] = {}
        self._audit_events: list[dict[str, str]] = []
        self._db: sqlite3.Connection | None = None
        self._fts_available = False
        if db_path is not None:
            path = Path(db_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(path, check_same_thread=False)
            self._initialize_database()
            self._load_database()

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def reset(self) -> None:
        """Clear all memory items, proposals, and claims from memory and database."""
        self._items.clear()
        self._revisions.clear()
        self._proposals.clear()
        self._source_events.clear()
        self._claims.clear()
        self._behavioral_directives.clear()
        self._audit_events.clear()
        if self._db is not None:
            self._db.execute("DELETE FROM memories")
            self._db.execute("DELETE FROM memory_revisions")
            self._db.execute("DELETE FROM memory_proposal_claims")
            self._db.execute("DELETE FROM memory_proposals")
            self._db.execute("DELETE FROM source_events")
            self._db.execute("DELETE FROM versioned_claims")
            if self._fts_available:
                self._db.execute("DELETE FROM versioned_claims_fts")
            self._db.execute("DELETE FROM behavioral_directives")
            self._db.commit()

    def _persist_revision(self, revision: MemoryRevision) -> None:
        if self._db is not None:
            self._db.execute(
                "INSERT INTO memory_revisions (memory_id, revision, content, changed_at, change_reason) VALUES (?, ?, ?, ?, ?)",
                (revision.memory_id, revision.revision, revision.content, revision.changed_at, revision.change_reason),
            )
            self._db.commit()

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
            CREATE TABLE IF NOT EXISTS memory_proposal_claims (
                proposal_id TEXT PRIMARY KEY, subject TEXT NOT NULL, predicate TEXT NOT NULL,
                value TEXT, claim_type TEXT NOT NULL, source_event_id TEXT
            );
            CREATE TABLE IF NOT EXISTS memory_audit_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT, memory_id TEXT, event_type TEXT NOT NULL,
                occurred_at TEXT NOT NULL, detail TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS source_events (
                event_id TEXT PRIMARY KEY, source_type TEXT NOT NULL, occurred_at TEXT NOT NULL,
                payload TEXT NOT NULL, schema_version INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS versioned_claims (
                claim_id TEXT PRIMARY KEY, subject TEXT NOT NULL, predicate TEXT NOT NULL,
                value TEXT NOT NULL, claim_type TEXT NOT NULL, source_event_id TEXT NOT NULL,
                provenance TEXT NOT NULL, authority TEXT NOT NULL, status TEXT NOT NULL,
                sensitivity TEXT NOT NULL, allowed_audiences TEXT NOT NULL, user_confirmation TEXT NOT NULL,
                confidence REAL NOT NULL, asserted_at TEXT NOT NULL, valid_from TEXT, valid_until TEXT,
                supersedes TEXT, replaces TEXT, schema_version INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS behavioral_directives (
                directive_id TEXT PRIMARY KEY, memory_class TEXT NOT NULL,
                domain TEXT NOT NULL, subject TEXT NOT NULL, predicate TEXT NOT NULL,
                value TEXT NOT NULL, activation TEXT NOT NULL, scope TEXT NOT NULL,
                behavior TEXT NOT NULL, status TEXT NOT NULL, source_type TEXT NOT NULL,
                source_event_id TEXT NOT NULL, confirmed_by TEXT NOT NULL,
                created_at TEXT NOT NULL, valid_from TEXT, valid_until TEXT,
                supersedes_id TEXT, sensitivity TEXT NOT NULL, confidence REAL NOT NULL
            );
            """
        )
        self._migrate_behavioral_directives_schema()
        try:
            self._db.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS versioned_claims_fts "
                "USING fts5(claim_id UNINDEXED, subject, predicate, value, tokenize='unicode61')"
            )
            self._fts_available = True
        except sqlite3.OperationalError:
            self._fts_available = False
        self._db.commit()

    def _migrate_behavioral_directives_schema(self) -> None:
        """Upgrade the six-column behavioral-memory prototype without data loss."""
        assert self._db is not None
        expected = (
            "directive_id", "memory_class", "domain", "subject", "predicate",
            "value", "activation", "scope", "behavior", "status",
            "source_type", "source_event_id", "confirmed_by", "created_at",
            "valid_from", "valid_until", "supersedes_id", "sensitivity",
            "confidence",
        )
        columns = tuple(row[1] for row in self._db.execute("PRAGMA table_info(behavioral_directives)"))
        if columns == expected:
            return
        legacy = ("directive_id", "memory_class", "activation", "instruction", "frequency", "created_at")
        if columns != legacy:
            raise sqlite3.OperationalError(
                "unsupported behavioral_directives schema; expected v1 or v2 columns"
            )

        rows = tuple(self._db.execute(
            "SELECT directive_id, memory_class, activation, instruction, frequency, created_at "
            "FROM behavioral_directives"
        ))
        with self._db:
            self._db.execute("ALTER TABLE behavioral_directives RENAME TO behavioral_directives_v1")
            self._db.execute(
                "CREATE TABLE behavioral_directives ("
                "directive_id TEXT PRIMARY KEY, memory_class TEXT NOT NULL, domain TEXT NOT NULL, "
                "subject TEXT NOT NULL, predicate TEXT NOT NULL, value TEXT NOT NULL, "
                "activation TEXT NOT NULL, scope TEXT NOT NULL, behavior TEXT NOT NULL, "
                "status TEXT NOT NULL, source_type TEXT NOT NULL, source_event_id TEXT NOT NULL, "
                "confirmed_by TEXT NOT NULL, created_at TEXT NOT NULL, valid_from TEXT, "
                "valid_until TEXT, supersedes_id TEXT, sensitivity TEXT NOT NULL, confidence REAL NOT NULL)"
            )
            for directive_id, memory_class, activation, instruction, frequency, created_at in rows:
                domain = memory_class if memory_class in {"identity", "relationship"} else "behavior"
                self._db.execute(
                    "INSERT INTO behavioral_directives (directive_id, memory_class, domain, subject, predicate, value, "
                    "activation, scope, behavior, status, source_type, source_event_id, confirmed_by, created_at, "
                    "valid_from, valid_until, supersedes_id, sensitivity, confidence) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        directive_id, memory_class, domain, "siduri", "legacy_instruction", instruction,
                        activation, json.dumps({"recipient_ids": [], "audiences": [], "session_modes": []}),
                        json.dumps({"instruction": instruction, "frequency": frequency, "preferred_positions": []}),
                        "confirmed", "behavioral_memory_v1_migration", f"legacy:{directive_id}",
                        "legacy_storage", created_at, None, None, None, "private", 1.0,
                    ),
                )
            self._db.execute("DROP TABLE behavioral_directives_v1")

    def _load_database(self) -> None:
        assert self._db is not None
        for row in self._db.execute("SELECT * FROM memories"):
            self._items[row[0]] = MemoryItem(row[1], row[2], row[3], frozenset(json.loads(row[4])), row[5], row[0], row[6], row[7], row[8], row[9], bool(row[10]), row[11])
        for row in self._db.execute("SELECT memory_id, revision, content, changed_at, change_reason FROM memory_revisions ORDER BY id"):
            self._revisions.setdefault(row[0], []).append(MemoryRevision(*row))
        for row in self._db.execute("SELECT * FROM memory_proposals"):
            self._proposals[row[0]] = MemoryProposal(row[1], row[2], row[3], frozenset(json.loads(row[4])), row[0], row[5])
        for row in self._db.execute("SELECT proposal_id, subject, predicate, value, claim_type, source_event_id FROM memory_proposal_claims"):
            proposal = self._proposals.get(row[0])
            if proposal is not None:
                self._proposals[row[0]] = replace(
                    proposal,
                    subject=row[1],
                    predicate=row[2],
                    value=row[3],
                    claim_type=row[4],
                    source_event_id=row[5],
                )
        for row in self._db.execute("SELECT memory_id, event_type, occurred_at, detail FROM memory_audit_events ORDER BY event_id"):
            self._audit_events.append({"memory_id": row[0] or "", "event_type": row[1], "occurred_at": row[2], "detail": row[3]})
        for row in self._db.execute("SELECT * FROM source_events"):
            self._source_events[row[0]] = SourceEvent(row[0], row[1], row[2], json.loads(row[3]), row[4])
        for row in self._db.execute("SELECT * FROM versioned_claims"):
            self._claims[row[0]] = VersionedClaim(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9], tuple(json.loads(row[10])), row[11], row[12], row[13], row[14], row[15], row[16], row[17], row[18])
        if self._fts_available:
            self._db.execute("DELETE FROM versioned_claims_fts")
            self._db.executemany(
                "INSERT INTO versioned_claims_fts (claim_id, subject, predicate, value) VALUES (?, ?, ?, ?)",
                ((claim.claim_id, claim.subject, claim.predicate, claim.value) for claim in self._claims.values()),
            )
            self._db.commit()
        for row in self._db.execute("SELECT * FROM behavioral_directives"):
            scope_data = json.loads(row[7])
            scope = Scope(tuple(scope_data.get("recipient_ids", [])), tuple(scope_data.get("audiences", [])), tuple(scope_data.get("session_modes", [])))
            behavior_data = json.loads(row[8])
            behavior = BehaviorDef(behavior_data.get("instruction", ""), behavior_data.get("frequency", "occasional"), tuple(behavior_data.get("preferred_positions", [])))
            self._behavioral_directives[row[0]] = BehavioralDirective(row[0], row[1], row[2], row[3], row[4], row[5], row[6], scope, behavior, row[9], row[10], row[11], row[12], row[13], row[14], row[15], row[16], row[17], row[18])

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
        revision = MemoryRevision(item.memory_id, 1, item.content, utc_now(), "created")
        self._revisions[item.memory_id] = [revision]
        self._persist_item(item)
        self._persist_revision(revision)
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
        revision = MemoryRevision(memory_id, updated.revision, content, utc_now(), reason)
        self._revisions[memory_id].append(revision)
        self._persist_item(updated)
        self._persist_revision(revision)
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
        self._persist_revision(deletion_revision)
        self._audit("deleted", memory_id, reason)

    def supersede(self, memory_id: str, replacement: MemoryItem, reason: str = "superseded") -> MemoryItem:
        current = self._items.get(memory_id)
        if current is None or current.deleted:
            raise KeyError(memory_id)
        self._items[memory_id] = replace(current, superseded_by=replacement.memory_id, revision=current.revision + 1)
        self._persist_item(self._items[memory_id])
        supersede_revision = MemoryRevision(memory_id, current.revision + 1, current.content, utc_now(), reason)
        self._revisions[memory_id].append(supersede_revision)
        self._persist_revision(supersede_revision)
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
        self._validate_proposal(proposal)
        self._proposals[proposal.proposal_id] = proposal
        self._persist_proposal(proposal)
        self._audit("proposal_created", None, proposal.proposal_id)
        return proposal

    def proposals(self) -> tuple[MemoryProposal, ...]:
        return tuple(self._proposals.values())

    def approve(self, proposal_id: str) -> MemoryItem:
        proposal = self._proposals[proposal_id]
        if proposal.status != "pending":
            raise ValueError(f"proposal is already {proposal.status}")
        item = self.create(MemoryItem(content=proposal.content, provenance=proposal.provenance, sensitivity=proposal.sensitivity, allowed_audiences=proposal.allowed_audiences))
        source_event_id = proposal.source_event_id
        if source_event_id is None:
            source_event = self.add_source_event(SourceEvent(
                event_id=f"evt_{uuid4().hex}",
                source_type="operator_memory_proposal",
                occurred_at=utc_now(),
                payload={"content": proposal.content},
            ))
            source_event_id = source_event.event_id
        previous = next((
            claim for claim in sorted(self._claims.values(), key=lambda candidate: candidate.asserted_at, reverse=True)
            if claim.status == "confirmed"
            and claim.subject == proposal.subject
            and claim.predicate == proposal.predicate
            and claim.value != (proposal.value or proposal.content)
            and claim.predicate in SINGLE_VALUE_PREDICATES
        ), None)
        self.add_claim(VersionedClaim(
            claim_id=f"claim_{uuid4().hex}",
            subject=proposal.subject,
            predicate=proposal.predicate,
            value=proposal.value or proposal.content,
            claim_type=proposal.claim_type,
            source_event_id=source_event_id,
            provenance=proposal.provenance,
            authority="user_correction" if previous else "user_explicit",
            status="confirmed",
            sensitivity=proposal.sensitivity,
            allowed_audiences=tuple(sorted(proposal.allowed_audiences)),
            user_confirmation="explicit",
            supersedes=previous.claim_id if previous else None,
        ))
        self._proposals[proposal_id] = replace(proposal, status="approved")
        self._persist_proposal(self._proposals[proposal_id])
        self._audit("proposal_approved", item.memory_id, proposal_id)
        return item

    def reject(self, proposal_id: str) -> MemoryProposal:
        proposal = self._proposals[proposal_id]
        if proposal.status != "pending":
            raise ValueError(f"proposal is already {proposal.status}")
        self._proposals[proposal_id] = replace(proposal, status="rejected")
        self._persist_proposal(self._proposals[proposal_id])
        self._audit("proposal_rejected", None, proposal_id)
        return self._proposals[proposal_id]

    def update_proposal(self, proposal_id: str, *, content: str, sensitivity: str | None = None, allowed_audiences: frozenset[str] | None = None) -> MemoryProposal:
        proposal = self._proposals[proposal_id]
        if proposal.status != "pending":
            raise ValueError(f"proposal is already {proposal.status}")
        if not content.strip() or len(content) > 2000:
            raise ValueError("proposal content must be non-empty and bounded")
        updated = replace(proposal, content=content.strip(), sensitivity=sensitivity or proposal.sensitivity,
                          allowed_audiences=allowed_audiences if allowed_audiences is not None else proposal.allowed_audiences)
        self._validate_proposal(updated)
        self._proposals[proposal_id] = updated
        self._persist_proposal(updated)
        self._audit("proposal_updated", None, proposal_id)
        return updated

    @staticmethod
    def _validate_proposal(proposal: MemoryProposal) -> None:
        if not proposal.content.strip() or len(proposal.content) > 2000:
            raise ValueError("proposal content must be non-empty and bounded")
        if proposal.sensitivity not in {"public", "stream_safe", "private", "secret"}:
            raise ValueError("proposal sensitivity is invalid")
        if len(proposal.provenance) > 160 or not proposal.provenance.strip():
            raise ValueError("proposal provenance is invalid")
        if len(proposal.allowed_audiences) > 8 or any(not isinstance(audience, str) or not audience or len(audience) > 64 for audience in proposal.allowed_audiences):
            raise ValueError("proposal audiences are invalid")
        if not proposal.subject.strip() or len(proposal.subject) > 128:
            raise ValueError("proposal subject is invalid")
        if not proposal.predicate.strip() or len(proposal.predicate) > 96:
            raise ValueError("proposal predicate is invalid")
        if proposal.value is not None and (not proposal.value.strip() or len(proposal.value) > 2000):
            raise ValueError("proposal value is invalid")
        if proposal.claim_type not in {"semantic", "preference", "episodic", "relationship"}:
            raise ValueError("proposal claim type is invalid")
        if proposal.source_event_id is not None and not proposal.source_event_id.strip():
            raise ValueError("proposal source event is invalid")

    def _persist_proposal(self, proposal: MemoryProposal) -> None:
        if self._db is not None:
            self._db.execute("INSERT OR REPLACE INTO memory_proposals VALUES (?, ?, ?, ?, ?, ?)", (proposal.proposal_id, proposal.content, proposal.provenance, proposal.sensitivity, json.dumps(sorted(proposal.allowed_audiences)), proposal.status))
            self._db.execute(
                "INSERT OR REPLACE INTO memory_proposal_claims VALUES (?, ?, ?, ?, ?, ?)",
                (proposal.proposal_id, proposal.subject, proposal.predicate, proposal.value, proposal.claim_type, proposal.source_event_id),
            )
            self._db.commit()

    def add_source_event(self, event: SourceEvent) -> SourceEvent:
        self._source_events[event.event_id] = event
        if self._db is not None:
            self._db.execute("INSERT OR REPLACE INTO source_events VALUES (?, ?, ?, ?, ?)", (event.event_id, event.source_type, event.occurred_at, json.dumps(event.payload), event.schema_version))
            self._db.commit()
        return event

    def get_source_event(self, event_id: str) -> SourceEvent | None:
        return self._source_events.get(event_id)

    def add_claim(self, claim: VersionedClaim) -> VersionedClaim:
        if claim.source_event_id not in self._source_events:
            raise ValueError(f"source event {claim.source_event_id} not found")
        if claim.supersedes:
            previous = self._claims.get(claim.supersedes)
            if previous is None:
                raise ValueError(f"superseded claim {claim.supersedes} not found")
            if previous.status in {"confirmed", "session_only"}:
                self._claims[previous.claim_id] = replace(previous, status="superseded", valid_until=claim.asserted_at)
                self._persist_claim(self._claims[previous.claim_id])
        self._claims[claim.claim_id] = claim
        self._persist_claim(claim)
        return claim

    def _persist_claim(self, claim: VersionedClaim) -> None:
        if self._db is not None:
            self._db.execute("INSERT OR REPLACE INTO versioned_claims VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (claim.claim_id, claim.subject, claim.predicate, claim.value, claim.claim_type, claim.source_event_id, claim.provenance, claim.authority, claim.status, claim.sensitivity, json.dumps(list(claim.allowed_audiences)), claim.user_confirmation, claim.confidence, claim.asserted_at, claim.valid_from, claim.valid_until, claim.supersedes, claim.replaces, claim.schema_version))
            if self._fts_available:
                self._db.execute("DELETE FROM versioned_claims_fts WHERE claim_id = ?", (claim.claim_id,))
                self._db.execute(
                    "INSERT INTO versioned_claims_fts (claim_id, subject, predicate, value) VALUES (?, ?, ?, ?)",
                    (claim.claim_id, claim.subject, claim.predicate, claim.value),
                )
            self._db.commit()

    def get_claim(self, claim_id: str) -> VersionedClaim | None:
        return self._claims.get(claim_id)

    def claims(self) -> tuple[VersionedClaim, ...]:
        return tuple(self._claims.values())

    @staticmethod
    def _claim_tokens(value: str) -> set[str]:
        return {token for token in re.findall(r"[a-z0-9]+", value.casefold()) if len(token) > 1}

    def query_claims(
        self,
        recipient: Recipient,
        *,
        subject: str | None = None,
        predicate: str | None = None,
        limit: int = 20,
    ) -> tuple[VersionedClaim, ...]:
        """Deterministically query current claims before fuzzy retrieval is needed."""
        now = datetime.now(timezone.utc)
        active_claims = [claim for claim in self.claims() if claim.status in {"confirmed", "session_only"}]
        superseded_ids = {claim.supersedes for claim in active_claims if claim.supersedes}
        result: list[VersionedClaim] = []
        for claim in active_claims:
            if claim.claim_id in superseded_ids:
                continue
            if claim.valid_from and datetime.fromisoformat(claim.valid_from) > now:
                continue
            if claim.valid_until and datetime.fromisoformat(claim.valid_until) <= now:
                continue
            if claim.sensitivity in {"private", "secret"} and recipient not in {Recipient.MASTER_PRIVATE, Recipient.SILENT_OPERATOR_NOTE}:
                continue
            if claim.allowed_audiences and recipient.value not in claim.allowed_audiences:
                continue
            if subject is not None and claim.subject.casefold() != subject.casefold():
                continue
            if predicate is not None and claim.predicate.casefold() != predicate.casefold():
                continue
            result.append(claim)
        result.sort(key=lambda claim: claim.asserted_at, reverse=True)
        return tuple(result[:limit])

    def _fts_claim_scores(self, terms: set[str], limit: int) -> dict[str, float]:
        if self._db is None or not self._fts_available or not terms:
            return {}
        query = " OR ".join(f'"{term}"*' for term in sorted(terms))
        try:
            rows = self._db.execute(
                "SELECT claim_id, bm25(versioned_claims_fts, 0.0, 3.0, 5.0, 1.0) "
                "FROM versioned_claims_fts WHERE versioned_claims_fts MATCH ? "
                "ORDER BY bm25(versioned_claims_fts, 0.0, 3.0, 5.0, 1.0) LIMIT ?",
                (query, limit),
            )
        except sqlite3.OperationalError:
            return {}
        return {str(claim_id): 1.0 / (1.0 + abs(float(rank))) for claim_id, rank in rows}

    def retrieve_claims(self, query: str, recipient: Recipient, limit: int = 5) -> tuple[VersionedClaim, ...]:
        terms = self._claim_tokens(query)
        if {"me", "my", "mine", "i"} & terms:
            terms.update({"primary", "user"})
        if {"genshin", "game", "account", "uid", "server"} & terms:
            terms.update({"genshin", "account"})
        fts_scores = self._fts_claim_scores(terms, max(limit * 4, 20))
        scored: list[tuple[int, float, str, VersionedClaim]] = []
        for claim in self.query_claims(recipient, limit=max(len(self._claims), limit)):
            subject_tokens = self._claim_tokens(claim.subject)
            predicate_tokens = self._claim_tokens(claim.predicate)
            value_tokens = self._claim_tokens(claim.value)
            score = (
                4 * len(terms & predicate_tokens)
                + 3 * len(terms & subject_tokens)
                + len(terms & value_tokens)
            )
            if claim.claim_id in fts_scores:
                score += 2
            if score:
                authority_bonus = {
                    "user_correction": 1.0,
                    "user_explicit": 0.9,
                    "import": 0.8,
                    "repeated_dialogue": 0.6,
                    "inference": 0.3,
                    "observation": 0.1,
                }.get(claim.authority, 0.0)
                scored.append((score, authority_bonus + claim.confidence + fts_scores.get(claim.claim_id, 0.0), claim.asserted_at, claim))
        scored.sort(key=lambda pair: (pair[0], pair[1], pair[2]), reverse=True)
        return tuple(claim for *_, claim in scored[:limit])

    def add_behavioral_directive(self, directive: BehavioralDirective) -> BehavioralDirective:
        self._behavioral_directives[directive.directive_id] = directive
        if self._db is not None:
            self._db.execute(
                "INSERT OR REPLACE INTO behavioral_directives (directive_id, memory_class, domain, subject, predicate, value, "
                "activation, scope, behavior, status, source_type, source_event_id, confirmed_by, created_at, valid_from, "
                "valid_until, supersedes_id, sensitivity, confidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (directive.directive_id, directive.memory_class, directive.domain, directive.subject, directive.predicate, directive.value, directive.activation, json.dumps(directive.scope.to_dict()), json.dumps(directive.behavior.to_dict()), directive.status, directive.source_type, directive.source_event_id, directive.confirmed_by, directive.created_at, directive.valid_from, directive.valid_until, directive.supersedes_id, directive.sensitivity, directive.confidence)
            )
            self._db.commit()
        return directive

    def approve_behavioral_directive(self, directive_id: str) -> BehavioralDirective:
        directive = self.get_behavioral_directive(directive_id)
        if directive is None:
            raise KeyError(directive_id)
        if directive.status != "pending":
            raise ValueError(f"directive is already {directive.status}")
        updated = replace(directive, status="confirmed", confirmed_by="primary_user")
        self.add_behavioral_directive(updated)
        if updated.supersedes_id:
            previous = self.get_behavioral_directive(updated.supersedes_id)
            if previous is not None and previous.status == "confirmed":
                self.add_behavioral_directive(replace(previous, status="superseded"))
        if updated.source_event_id not in self._source_events:
            self.add_source_event(SourceEvent(
                event_id=updated.source_event_id,
                source_type=updated.source_type,
                occurred_at=updated.created_at,
                payload={"subject": updated.subject, "predicate": updated.predicate, "value": updated.value},
            ))
        duplicate = any(
            claim.source_event_id == updated.source_event_id
            and claim.subject == updated.subject
            and claim.predicate == updated.predicate
            and claim.value == updated.value
            and claim.status == "confirmed"
            for claim in self._claims.values()
        )
        if not duplicate:
            self.add_claim(VersionedClaim(
                claim_id=f"claim_{uuid4().hex}",
                subject=updated.subject,
                predicate=updated.predicate,
                value=updated.value,
                claim_type="relationship" if updated.domain == "relationship" else "semantic",
                source_event_id=updated.source_event_id,
                provenance=updated.source_type,
                authority="user_explicit",
                status="confirmed",
                sensitivity=updated.sensitivity,
                allowed_audiences=updated.scope.audiences,
                user_confirmation="explicit",
                confidence=updated.confidence,
            ))
        self._audit("behavioral_directive_approved", updated.directive_id, updated.source_event_id)
        return updated

    def reject_behavioral_directive(self, directive_id: str) -> BehavioralDirective:
        directive = self.get_behavioral_directive(directive_id)
        if directive is None:
            raise KeyError(directive_id)
        if directive.status != "pending":
            raise ValueError(f"directive is already {directive.status}")
        updated = replace(directive, status="rejected", confirmed_by="primary_user")
        return self.add_behavioral_directive(updated)

    def disable_behavioral_directive(self, directive_id: str) -> BehavioralDirective:
        directive = self.get_behavioral_directive(directive_id)
        if directive is None:
            raise KeyError(directive_id)
        updated = replace(directive, activation="disabled", confirmed_by="primary_user")
        return self.add_behavioral_directive(updated)

    def revoke_behavioral_directive(self, directive_id: str) -> BehavioralDirective:
        directive = self.get_behavioral_directive(directive_id)
        if directive is None:
            raise KeyError(directive_id)
        updated = replace(directive, status="revoked", confirmed_by="primary_user")
        return self.add_behavioral_directive(updated)

    def get_behavioral_directive(self, directive_id: str) -> BehavioralDirective | None:
        return self._behavioral_directives.get(directive_id)

    def list_all_behavioral_directives(self) -> tuple[BehavioralDirective, ...]:
        return tuple(self._behavioral_directives.values())

    def list_active_behavioral_directives(self) -> tuple[BehavioralDirective, ...]:
        return tuple(d for d in self._behavioral_directives.values() if d.activation != "disabled")
