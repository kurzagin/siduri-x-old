from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import time
import json
import sqlite3
import threading
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4


SCHEMA_VERSION = 1


class Platform(StrEnum):
    YOUTUBE = "youtube"
    TWITCH = "twitch"


class ActionStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def bounded_text(value: object, *, field_name: str, limit: int = 4000) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    value = " ".join(value.split())
    if not value or len(value) > limit:
        raise ValueError(f"{field_name} must be non-empty and bounded")
    return value


@dataclass(frozen=True)
class PlatformEvent:
    platform: Platform
    event_type: str
    source_message_id: str
    channel_id: str
    author_id: str
    author_display_name: str
    text: str
    occurred_at: str
    event_id: str = field(default_factory=lambda: f"platform_evt_{uuid4().hex}")
    metadata: dict[str, str] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION
    privacy_class: str = "untrusted_public"

    def __post_init__(self) -> None:
        if not self.source_message_id or len(self.source_message_id) > 256:
            raise ValueError("source_message_id is invalid")
        object.__setattr__(self, "channel_id", bounded_text(self.channel_id, field_name="channel_id", limit=256))
        object.__setattr__(self, "author_id", bounded_text(self.author_id, field_name="author_id", limit=256))
        object.__setattr__(self, "author_display_name", bounded_text(self.author_display_name, field_name="author_display_name", limit=256))
        object.__setattr__(self, "text", bounded_text(self.text, field_name="text"))
        if self.event_type not in {"chat_message", "chat_notice"}:
            raise ValueError("event_type is invalid")
        if len(self.metadata) > 16:
            raise ValueError("metadata is too large")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "source": self.platform.value,
            "privacy_class": self.privacy_class,
            "payload": {
                "source_message_id": self.source_message_id,
                "channel_id": self.channel_id,
                "author_id": self.author_id,
                "author_display_name": self.author_display_name,
                "text": self.text,
                "metadata": dict(self.metadata),
            },
        }


class PlatformEventSink(Protocol):
    def ingest(self, event: PlatformEvent) -> bool: ...


class PlatformEventHub:
    """Bounded, duplicate-resistant store for untrusted inbound platform events."""

    def __init__(self, max_events: int = 200, max_seen_ids: int = 1000, guard: "PlatformIngressGuard | None" = None) -> None:
        if max_events < 1 or max_seen_ids < 1:
            raise ValueError("event bounds must be positive")
        self._max_events = max_events
        self._max_seen_ids = max_seen_ids
        self._events: list[PlatformEvent] = []
        self._seen: list[str] = []
        self._guard = guard

    def ingest(self, event: PlatformEvent) -> bool:
        if event.source_message_id in self._seen or (self._guard is not None and not self._guard.accept(event)):
            return False
        self._seen.append(event.source_message_id)
        self._seen = self._seen[-self._max_seen_ids:]
        self._events.append(event)
        self._events = self._events[-self._max_events:]
        return True

    def events(self, platform: Platform | None = None) -> tuple[PlatformEvent, ...]:
        if platform is None:
            return tuple(self._events)
        return tuple(event for event in self._events if event.platform == platform)

    def clear(self) -> None:
        self._events.clear()
        self._seen.clear()


class PlatformIngressGuard:
    """Small in-memory spam/rate guard; platform moderation remains platform-owned."""

    def __init__(self, max_messages_per_window: int = 20, window_seconds: int = 30, duplicate_window_seconds: int = 20) -> None:
        if min(max_messages_per_window, window_seconds, duplicate_window_seconds) < 1:
            raise ValueError("ingress limits must be positive")
        self.max_messages_per_window = max_messages_per_window
        self.window_seconds = window_seconds
        self.duplicate_window_seconds = duplicate_window_seconds
        self._author_times: dict[tuple[Platform, str], list[float]] = {}
        self._recent_text: dict[tuple[Platform, str, str], float] = {}

    def accept(self, event: PlatformEvent, *, now: float | None = None) -> bool:
        current = time.time() if now is None else now
        author_key = (event.platform, event.author_id)
        times = [value for value in self._author_times.get(author_key, []) if current - value < self.window_seconds]
        text_key = (event.platform, event.author_id, event.text.casefold())
        prior = self._recent_text.get(text_key)
        if prior is not None and current - prior < self.duplicate_window_seconds:
            self._author_times[author_key] = times
            return False
        if len(times) >= self.max_messages_per_window:
            self._author_times[author_key] = times
            return False
        times.append(current)
        self._author_times[author_key] = times
        self._recent_text[text_key] = current
        self._recent_text = {key: value for key, value in self._recent_text.items() if current - value < self.duplicate_window_seconds}
        return True


@dataclass(frozen=True)
class OutboundAction:
    platform: Platform
    action_type: str
    target_id: str
    text: str
    evidence_ids: tuple[str, ...] = ()
    action_id: str = field(default_factory=lambda: f"platform_action_{uuid4().hex}")
    status: ActionStatus = ActionStatus.PROPOSED
    created_at: str = field(default_factory=utc_now)
    reviewed_at: str | None = None
    sent_at: str | None = None

    def __post_init__(self) -> None:
        if self.action_type != "chat_message":
            raise ValueError("only chat_message actions are currently supported")
        bounded_text(self.target_id, field_name="target_id", limit=256)
        bounded_text(self.text, field_name="text", limit=2000)
        if len(self.evidence_ids) > 16:
            raise ValueError("too many evidence IDs")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "action_id": self.action_id,
            "platform": self.platform.value,
            "action_type": self.action_type,
            "target_id": self.target_id,
            "text": self.text,
            "evidence_ids": list(self.evidence_ids),
            "status": self.status.value,
            "created_at": self.created_at,
            "reviewed_at": self.reviewed_at,
            "sent_at": self.sent_at,
        }


class ActionSender(Protocol):
    def send_message(self, target_id: str, text: str) -> str: ...


class OutboundActionService:
    """Thread-safe outbound approval queue with optional durable local audit storage."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._actions: dict[str, OutboundAction] = {}
        self._audit: list[dict[str, str]] = []
        self._lock = threading.RLock()
        self._db: sqlite3.Connection | None = None
        if db_path is not None:
            path = Path(db_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(path, check_same_thread=False)
            self._db.executescript(
                """
                CREATE TABLE IF NOT EXISTS platform_actions (
                    action_id TEXT PRIMARY KEY, platform TEXT NOT NULL, action_type TEXT NOT NULL,
                    target_id TEXT NOT NULL, text TEXT NOT NULL, evidence_ids TEXT NOT NULL,
                    status TEXT NOT NULL, created_at TEXT NOT NULL, reviewed_at TEXT, sent_at TEXT
                );
                CREATE TABLE IF NOT EXISTS platform_action_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, action_id TEXT NOT NULL,
                    event TEXT NOT NULL, occurred_at TEXT NOT NULL, receipt TEXT
                );
                """
            )
            self._db.commit()
            self._load()

    def close(self) -> None:
        with self._lock:
            if self._db is not None:
                self._db.close()
                self._db = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def _load(self) -> None:
        assert self._db is not None
        for row in self._db.execute("SELECT action_id, platform, action_type, target_id, text, evidence_ids, status, created_at, reviewed_at, sent_at FROM platform_actions ORDER BY created_at"):
            self._actions[row[0]] = OutboundAction(Platform(row[1]), row[2], row[3], row[4], tuple(json.loads(row[5])), row[0], ActionStatus(row[6]), row[7], row[8], row[9])
        for row in self._db.execute("SELECT action_id, event, occurred_at, receipt FROM platform_action_audit ORDER BY id"):
            entry = {"event": row[1], "action_id": row[0], "at": row[2]}
            if row[3] is not None:
                entry["receipt"] = row[3]
            self._audit.append(entry)

    def _persist(self, action: OutboundAction) -> None:
        if self._db is not None:
            self._db.execute(
                "INSERT OR REPLACE INTO platform_actions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (action.action_id, action.platform.value, action.action_type, action.target_id, action.text, json.dumps(list(action.evidence_ids)), action.status.value, action.created_at, action.reviewed_at, action.sent_at),
            )
            self._db.commit()

    def _record_audit(self, event: str, action_id: str, receipt: str | None = None) -> None:
        occurred_at = utc_now()
        entry = {"event": event, "action_id": action_id, "at": occurred_at}
        if receipt is not None:
            entry["receipt"] = receipt
        self._audit.append(entry)
        if self._db is not None:
            self._db.execute("INSERT INTO platform_action_audit (action_id, event, occurred_at, receipt) VALUES (?, ?, ?, ?)", (action_id, event, occurred_at, receipt))
            self._db.commit()

    def propose(self, action: OutboundAction) -> OutboundAction:
        with self._lock:
            if action.action_id in self._actions:
                raise ValueError("action ID already exists")
            self._actions[action.action_id] = action
            self._persist(action)
            self._record_audit("proposed", action.action_id)
            return action

    def get(self, action_id: str) -> OutboundAction | None:
        with self._lock:
            return self._actions.get(action_id)

    def list(self) -> tuple[OutboundAction, ...]:
        with self._lock:
            return tuple(self._actions.values())

    def approve(self, action_id: str, edited_text: str | None = None) -> OutboundAction:
        with self._lock:
            action = self._actions[action_id]
            if action.status != ActionStatus.PROPOSED:
                raise ValueError(f"action is already {action.status.value}")
            updated = replace(action, text=edited_text if edited_text is not None else action.text,
                              status=ActionStatus.APPROVED, reviewed_at=utc_now())
            self._actions[action_id] = updated
            self._persist(updated)
            self._record_audit("approved", action_id)
            return updated

    def reject(self, action_id: str) -> OutboundAction:
        with self._lock:
            action = self._actions[action_id]
            if action.status != ActionStatus.PROPOSED:
                raise ValueError(f"action is already {action.status.value}")
            updated = replace(action, status=ActionStatus.REJECTED, reviewed_at=utc_now())
            self._actions[action_id] = updated
            self._persist(updated)
            self._record_audit("rejected", action_id)
            return updated

    def send(self, action_id: str, sender: ActionSender) -> tuple[OutboundAction, str]:
        with self._lock:
            action = self._actions[action_id]
            if action.status != ActionStatus.APPROVED:
                raise ValueError("outbound action requires operator approval")
            receipt = sender.send_message(action.target_id, action.text)
            if not receipt or len(receipt) > 256:
                raise ValueError("platform sender returned an invalid receipt")
            updated = replace(action, status=ActionStatus.SENT, sent_at=utc_now())
            self._actions[action_id] = updated
            self._persist(updated)
            self._record_audit("sent", action_id, receipt)
            return updated, receipt

    def audit(self) -> tuple[dict[str, str], ...]:
        with self._lock:
            return tuple(self._audit)
