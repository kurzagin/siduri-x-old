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
