from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

PrivacyClass = Literal["public", "stream_safe", "private", "secret"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class EventEnvelope:
    event_type: str
    payload: dict[str, Any]
    source: str = "orchestrator"
    privacy_class: PrivacyClass = "stream_safe"
    event_id: str = field(default_factory=lambda: f"evt_{uuid4().hex}")
    schema_version: int = 1
    occurred_at: str = field(default_factory=now)
    session_id: str = "session_foundation"
    correlation_id: str = field(default_factory=lambda: f"corr_{uuid4().hex}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResponsePlan:
    recipient: str
    intent: str
    semantic_summary: str
    spoken_ja: str
    subtitle_en: str
    subtitle_id: str
    emotion: str = "observant"
    speech_priority: int = 50
    interruptible: bool = True
    evidence_ids: tuple[str, ...] = ()
    confidence: float = 1.0
    requires_operator_approval: bool = False
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["evidence_ids"] = list(self.evidence_ids)
        return result

    @classmethod
    def from_dict(cls, value: object, expected_recipient: str | None = None) -> "ResponsePlan":
        if not isinstance(value, dict):
            raise ValueError("response plan must be an object")
        string_fields = ("recipient", "intent", "semantic_summary", "spoken_ja", "subtitle_en", "subtitle_id")
        if any(not isinstance(value.get(field), str) or not value[field].strip() for field in string_fields):
            raise ValueError("response plan has missing or invalid text fields")
        if "emotion" in value and (not isinstance(value["emotion"], str) or not value["emotion"].strip()):
            raise ValueError("emotion must be a non-empty string")
        if expected_recipient is not None and value["recipient"] != expected_recipient:
            raise ValueError("response plan recipient does not match the requested audience")
        confidence = value.get("confidence", 1.0)
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        priority = value.get("speech_priority", 50)
        if isinstance(priority, bool) or not isinstance(priority, int) or not 0 <= priority <= 100:
            raise ValueError("speech_priority must be an integer between 0 and 100")
        interruptible = value.get("interruptible", True)
        approval = value.get("requires_operator_approval", False)
        if not isinstance(interruptible, bool) or not isinstance(approval, bool):
            raise ValueError("interruptible and requires_operator_approval must be booleans")
        evidence = value.get("evidence_ids", [])
        if not isinstance(evidence, list) or len(evidence) > 32 or not all(isinstance(item, str) and item and len(item) <= 128 for item in evidence):
            raise ValueError("evidence_ids must be a bounded list of non-empty strings")
        return cls(recipient=value["recipient"], intent=value["intent"], semantic_summary=value["semantic_summary"],
                   spoken_ja=value["spoken_ja"], subtitle_en=value["subtitle_en"], subtitle_id=value["subtitle_id"],
                   emotion=value.get("emotion", "observant") if isinstance(value.get("emotion", "observant"), str) else "observant",
                   speech_priority=priority, interruptible=interruptible,
                   evidence_ids=tuple(evidence), confidence=float(confidence), requires_operator_approval=approval,
                   schema_version=int(value.get("schema_version", 1)))


class MockProvider:
    capabilities = {"text_generation", "structured_generation"}

    def response(self) -> ResponsePlan:
        return ResponsePlan(
            recipient="master_stream",
            intent="system_commentary",
            semantic_summary="Siduri is online and observing the stream foundation.",
            spoken_ja="ご主人、記録 keeper の基盤は稼働中です。観測はまだ準備段階ですが、静かに待機しています。",
            subtitle_en="Master, the Records Keeper foundation is online. Observation is still in preparation, but I am quietly standing by.",
            subtitle_id="Master, fondasi Records Keeper sedang aktif. Observasi masih dalam tahap persiapan, tetapi aku menunggu dengan tenang.",
            emotion="idle",
            confidence=1.0,
        )
