from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InMemoryRepository:
    sessions: dict[str, dict[str, Any]] = field(default_factory=dict)
    audit_events: list[dict[str, Any]] = field(default_factory=list)

    def save_audit_event(self, event: dict[str, Any]) -> None:
        self.audit_events.append(event)

    def create_session(self, session_id: str, started_at: str) -> None:
        self.sessions[session_id] = {"session_id": session_id, "started_at": started_at, "status": "active"}
