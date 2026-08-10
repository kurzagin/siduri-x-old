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
    memory_proposals: tuple[dict[str, Any], ...] = ()
    behavioral_proposals: tuple[dict[str, Any], ...] = ()
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["evidence_ids"] = list(self.evidence_ids)
        result["memory_proposals"] = [dict(item) for item in self.memory_proposals]
        result["behavioral_proposals"] = [dict(item) for item in self.behavioral_proposals]
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
        raw_proposals = value.get("memory_proposals", [])
        if not isinstance(raw_proposals, list) or len(raw_proposals) > 4:
            raise ValueError("memory_proposals must be a bounded list")
        proposals: list[dict[str, Any]] = []
        for candidate in raw_proposals:
            if not isinstance(candidate, dict):
                raise ValueError("memory proposal must be an object")
            content = candidate.get("content")
            if not isinstance(content, str) or not content.strip() or len(content) > 2000:
                raise ValueError("memory proposal content is invalid")
            sensitivity = candidate.get("sensitivity", "private")
            if sensitivity not in {"public", "stream_safe", "private", "secret"}:
                sensitivity = "private"
            audiences = candidate.get("allowed_audiences", ["master_private"])
            provenance = candidate.get("provenance", "system_private_chat")
            if not isinstance(provenance, str) or not isinstance(audiences, list) or len(audiences) > 8 or not all(isinstance(item, str) and item for item in audiences):
                raise ValueError("memory proposal metadata is invalid")
            subject = candidate.get("subject", "primary_user")
            predicate = candidate.get("predicate", "note")
            claim_value = candidate.get("value", content)
            claim_type = candidate.get("claim_type", "semantic")
            if not isinstance(subject, str) or not subject.strip() or len(subject) > 128:
                raise ValueError("memory proposal subject is invalid")
            if not isinstance(predicate, str) or not predicate.strip() or len(predicate) > 96:
                raise ValueError("memory proposal predicate is invalid")
            if not isinstance(claim_value, str) or not claim_value.strip() or len(claim_value) > 2000:
                raise ValueError("memory proposal value is invalid")
            if claim_type not in {"semantic", "preference", "episodic", "relationship"}:
                raise ValueError("memory proposal claim_type is invalid")
            proposals.append({
                "content": content.strip(),
                "provenance": provenance[:160],
                "sensitivity": sensitivity,
                "allowed_audiences": audiences,
                "subject": subject.strip(),
                "predicate": predicate.strip(),
                "value": claim_value.strip(),
                "claim_type": claim_type,
            })

        raw_behavioral = value.get("behavioral_proposals", [])
        if not isinstance(raw_behavioral, list) or len(raw_behavioral) > 4:
            raise ValueError("behavioral_proposals must be a bounded list")
        behavioral_proposals: list[dict[str, Any]] = []
        for candidate in raw_behavioral:
            if not isinstance(candidate, dict):
                raise ValueError("behavioral proposal must be an object")
            runtime_effect = candidate.get("runtime_effect")
            legacy_class = candidate.get("memory_class")
            if runtime_effect is None:
                runtime_effect = {
                    "identity": "identity_context",
                    "relationship": "relationship_context",
                    "behavioral": "behavioral_rule",
                }.get(legacy_class)
            effect_to_class = {
                "identity_context": "identity",
                "relationship_context": "relationship",
                "behavioral_rule": "behavioral",
            }
            if runtime_effect not in effect_to_class:
                raise ValueError("behavioral proposal runtime_effect is invalid")
            knowledge_domain = candidate.get("knowledge_domain", candidate.get("domain", "semantic"))
            subject = candidate.get("subject")
            predicate = candidate.get("predicate")
            claim_value = candidate.get("value")
            if not isinstance(knowledge_domain, str) or not knowledge_domain.strip() or len(knowledge_domain) > 64:
                raise ValueError("behavioral proposal knowledge_domain is invalid")
            if not isinstance(subject, str) or not subject.strip() or len(subject) > 128:
                raise ValueError("behavioral proposal subject is invalid")
            if not isinstance(predicate, str) or not predicate.strip() or len(predicate) > 96:
                raise ValueError("behavioral proposal predicate is invalid")
            if not isinstance(claim_value, str) or not claim_value.strip() or len(claim_value) > 1000:
                raise ValueError("behavioral proposal value is invalid")
            activation = candidate.get("activation", "always_when_scope_matches")
            if activation not in {"always", "always_when_scope_matches"}:
                raise ValueError("behavioral proposal activation is invalid")
            raw_scope = candidate.get("scope", {})
            raw_behavior = candidate.get("behavior", {})
            if not isinstance(raw_scope, dict) or not isinstance(raw_behavior, dict):
                raise ValueError("behavioral proposal scope and behavior must be objects")
            scope: dict[str, list[str]] = {}
            for key in ("recipient_ids", "audiences", "session_modes"):
                items = raw_scope.get(key, [])
                if not isinstance(items, list) or len(items) > 8 or not all(isinstance(item, str) and 0 < len(item) <= 64 for item in items):
                    raise ValueError(f"behavioral proposal {key} is invalid")
                scope[key] = items
            instruction = raw_behavior.get("instruction", "")
            frequency = raw_behavior.get("frequency", "contextual")
            positions = raw_behavior.get("preferred_positions", [])
            if not isinstance(instruction, str) or len(instruction) > 500:
                raise ValueError("behavioral proposal instruction is invalid")
            if runtime_effect == "behavioral_rule" and not instruction.strip():
                raise ValueError("behavioral rule requires an instruction")
            if not isinstance(frequency, str) or not frequency.strip() or len(frequency) > 32:
                raise ValueError("behavioral proposal frequency is invalid")
            if not isinstance(positions, list) or len(positions) > 8 or not all(isinstance(item, str) and 0 < len(item) <= 32 for item in positions):
                raise ValueError("behavioral proposal preferred_positions is invalid")
            behavioral_proposals.append({
                "memory_class": effect_to_class[runtime_effect],
                "runtime_effect": runtime_effect,
                "knowledge_domain": knowledge_domain.strip(),
                "domain": knowledge_domain.strip(),
                "subject": subject.strip(),
                "predicate": predicate.strip(),
                "value": claim_value.strip(),
                "activation": activation,
                "scope": scope,
                "behavior": {
                    "instruction": instruction.strip(),
                    "frequency": frequency.strip(),
                    "preferred_positions": positions,
                },
            })

        return cls(recipient=value["recipient"], intent=value["intent"], semantic_summary=value["semantic_summary"],
                   spoken_ja=value["spoken_ja"], subtitle_en=value["subtitle_en"], subtitle_id=value["subtitle_id"],
                   emotion=value.get("emotion", "observant") if isinstance(value.get("emotion", "observant"), str) else "observant",
                   speech_priority=priority, interruptible=interruptible,
                   evidence_ids=tuple(evidence), confidence=float(confidence), requires_operator_approval=approval,
                   memory_proposals=tuple(proposals), behavioral_proposals=tuple(behavioral_proposals),
                   schema_version=int(value.get("schema_version", 1)))


class MockProvider:
    capabilities = {"text_generation", "structured_generation"}

    def response(self) -> ResponsePlan:
        return ResponsePlan(
            recipient="master_stream",
            intent="system_commentary",
            semantic_summary="System is online and observing the foundation.",
            spoken_ja="基盤は稼働中です。観測はまだ準備段階ですが、待機しています。",
            subtitle_en="The foundation is online. Observation is still in preparation, standing by.",
            subtitle_id="Fondasi sedang aktif. Observasi masih dalam tahap persiapan, dalam mode siaga.",
            emotion="idle",
            confidence=1.0,
        )
