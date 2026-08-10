from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class Recipient(StrEnum):
    MASTER_PRIVATE = "master_private"
    MASTER_STREAM = "master_stream"
    VIEWER_DIRECT = "viewer_direct"
    AUDIENCE_GENERAL = "audience_general"
    SYSTEM_COMMENTARY = "system_commentary"
    SILENT_OPERATOR_NOTE = "silent_operator_note"


PUBLIC_RECIPIENTS = frozenset({Recipient.MASTER_STREAM, Recipient.VIEWER_DIRECT, Recipient.AUDIENCE_GENERAL, Recipient.SYSTEM_COMMENTARY})


@dataclass(frozen=True)
class MeProfile:
    identity: dict[str, Any]
    relationship_with_siduri: dict[str, Any]
    communication: dict[str, Any]
    habits: dict[str, Any]
    interests: dict[str, Any]
    projects: dict[str, Any]
    privacy: dict[str, Any]
    schema_version: int = 1

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "MeProfile":
        required = ("identity", "relationship_with_siduri", "communication", "privacy")
        missing = [key for key in required if key not in value]
        if missing:
            raise ValueError(f"Me profile missing required sections: {', '.join(missing)}")
        return cls(
            identity=dict(value["identity"]),
            relationship_with_siduri=dict(value["relationship_with_siduri"]),
            communication=dict(value.get("communication", {})),
            habits=dict(value.get("habits", {})),
            interests=dict(value.get("interests", {})),
            projects=dict(value.get("projects", {})),
            privacy=dict(value["privacy"]),
            schema_version=int(value.get("schema_version", 1)),
        )

    @classmethod
    def from_json_file(cls, path: str | Path) -> "MeProfile":
        with Path(path).open(encoding="utf-8") as handle:
            loaded = json.load(handle)
        if not isinstance(loaded, dict):
            raise ValueError("Me profile root must be an object")
        return cls.from_dict(loaded)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def stream_view(self) -> dict[str, Any]:
        allowed = set(self.privacy.get("fields_allowed_on_stream", []))
        identity = {key: value for key, value in self.identity.items() if key in allowed}
        projects = {key: value for key, value in self.projects.items() if key in allowed}
        return {"identity": identity, "projects": projects, "relationship_with_siduri": self.relationship_with_siduri, "communication": self.communication, "habits": self.habits, "interests": self.interests}


@dataclass(frozen=True)
class RelationshipPolicy:
    creator_name: str = "Kur Zagin"
    private_address: str = "Master"
    stream_address: str = "Master"
    public_recipient_modes: frozenset[Recipient] = PUBLIC_RECIPIENTS
    private_memory_modes: frozenset[Recipient] = frozenset({Recipient.MASTER_PRIVATE, Recipient.SILENT_OPERATOR_NOTE})

    def can_use_private_memory(self, recipient: Recipient) -> bool:
        return recipient in self.private_memory_modes


class RecipientClassifier:
    """Conservative heuristic until a reviewed classifier is introduced."""

    _private_markers = re.compile(r"\b(private|dm|direct message|off stream|secret)\b", re.I)
    _viewer_markers = re.compile(r"\b(viewer|chat|comment|audience)\b", re.I)

    def classify(self, *, speaker: str, is_live: bool, text: str, operator_only: bool = False) -> Recipient:
        if operator_only:
            return Recipient.SILENT_OPERATOR_NOTE
        if speaker.lower() in {"kur", "kur zagin", "master", "creator"}:
            if self._private_markers.search(text) or not is_live:
                return Recipient.MASTER_PRIVATE
            return Recipient.MASTER_STREAM
        if self._viewer_markers.search(text) or speaker.lower() not in {"siduri", "system"}:
            return Recipient.VIEWER_DIRECT
        return Recipient.SYSTEM_COMMENTARY


@dataclass(frozen=True)
class DisclosureDecision:
    allowed: bool
    reason: str
    redacted_fields: tuple[str, ...] = ()


class DisclosurePolicy:
    def __init__(self, relationship: RelationshipPolicy | None = None) -> None:
        self.relationship = relationship or RelationshipPolicy()

    def check_memory(self, *, recipient: Recipient, sensitivity: str, allowed_audiences: frozenset[str]) -> DisclosureDecision:
        if sensitivity in {"secret", "private"} and not self.relationship.can_use_private_memory(recipient):
            return DisclosureDecision(False, "private memory is not allowed for this recipient")
        if allowed_audiences and recipient.value not in allowed_audiences:
            return DisclosureDecision(False, "memory audience allowlist excludes this recipient")
        return DisclosureDecision(True, "memory is allowed for this recipient")

