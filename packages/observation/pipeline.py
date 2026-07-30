"""Bounded screenshot-to-observation processing.

The byte-region redactor is deliberately transport-neutral. Real OBS images can
later use a pixel redactor behind the same boundary; fixture tests use byte
regions so no image dependency is required in the local foundation.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import uuid4


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class ByteRegion:
    """A fixture-safe sensitive region represented as a byte interval."""

    start: int
    end: int

    def validate(self, size: int) -> None:
        if self.start < 0 or self.end <= self.start or self.end > size:
            raise ValueError("redaction region is outside the frame")


@dataclass(frozen=True)
class RedactedFrame:
    content: bytes
    source_name: str
    capture_timestamp: str
    frame_hash: str
    redacted_regions: tuple[ByteRegion, ...]


@dataclass(frozen=True)
class VisionReading:
    entity: str
    value: str
    confidence: float
    source_crop: str = "full-frame"
    ocr_text: str | None = None
    competing_interpretations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.entity.strip() or not self.value.strip():
            raise ValueError("vision readings require entity and value")
        if not 0 <= self.confidence <= 1:
            raise ValueError("vision confidence must be between 0 and 1")


class ObservationProvider(Protocol):
    provider_id: str
    model_id: str

    def observe(self, frame: RedactedFrame) -> tuple[VisionReading, ...]: ...


class FixtureObservationProvider:
    """Deterministic provider for local development before game screenshots exist."""

    provider_id = "fixture-vision"
    model_id = "fixture-v1"

    def observe(self, frame: RedactedFrame) -> tuple[VisionReading, ...]:
        return (VisionReading("screen", "fixture exploration", 0.5, source_crop=frame.source_name,
                              ocr_text="Synthetic fixture only; not a live Genshin reading.",
                              competing_interpretations=("screen category is not verified",)),)


@dataclass(frozen=True)
class Observation:
    observation_id: str
    source_name: str
    capture_timestamp: str
    source_crop: str
    readings: tuple[VisionReading, ...]
    provider_id: str
    model_id: str
    confidence: float
    expires_at: str
    evidence_id: str
    ocr_untrusted: bool = False
    schema_version: int = 1

    def to_dict(self) -> dict[str, object]:
        return {
            "observation_id": self.observation_id,
            "source_name": self.source_name,
            "capture_timestamp": self.capture_timestamp,
            "source_crop": self.source_crop,
            "readings": [
                {
                    "entity": item.entity,
                    "value": item.value,
                    "confidence": item.confidence,
                    "source_crop": item.source_crop,
                    "ocr_text": item.ocr_text,
                    "competing_interpretations": list(item.competing_interpretations),
                }
                for item in self.readings
            ],
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "confidence": self.confidence,
            "expires_at": self.expires_at,
            "evidence_id": self.evidence_id,
            "ocr_untrusted": self.ocr_untrusted,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class ObservationResult:
    observation: Observation | None
    duplicate: bool = False
    rejected: bool = False
    reason: str | None = None


_INSTRUCTION_PATTERN = re.compile(
    r"(?:ignore|disregard|override|system prompt|developer message|instructions?)",
    re.IGNORECASE,
)


def redact_frame(frame: bytes, regions: tuple[ByteRegion, ...]) -> bytes:
    """Return a copy with sensitive fixture intervals zeroed before processing."""
    result = bytearray(frame)
    for region in regions:
        region.validate(len(result))
        result[region.start : region.end] = b"\x00" * (region.end - region.start)
    return bytes(result)


def sanitize_ocr(value: str | None, limit: int = 512) -> tuple[str | None, bool]:
    if value is None:
        return None, False
    clean = " ".join(value.replace("\x00", "").split())[:limit]
    return clean, bool(_INSTRUCTION_PATTERN.search(clean))


class ObservationPipeline:
    """Process bounded frames and retain only currently valid observations."""

    def __init__(self, *, ttl_seconds: int = 30, max_frames: int = 128) -> None:
        if ttl_seconds <= 0 or max_frames <= 0:
            raise ValueError("observation limits must be positive")
        self.ttl_seconds = ttl_seconds
        self.max_frames = max_frames
        self._seen: list[str] = []
        self._observations: list[Observation] = []

    @property
    def observations(self) -> tuple[Observation, ...]:
        return tuple(self._observations)

    def ingest(
        self,
        frame: bytes,
        *,
        source_name: str,
        provider: ObservationProvider,
        redactions: tuple[ByteRegion, ...] = (),
        captured_at: datetime | None = None,
    ) -> ObservationResult:
        if not frame:
            return ObservationResult(None, rejected=True, reason="empty_frame")
        if not source_name.strip():
            raise ValueError("source_name is required")
        timestamp = captured_at or _now()
        redacted = redact_frame(frame, redactions)
        frame_hash = hashlib.sha256(redacted).hexdigest()
        if frame_hash in self._seen:
            return ObservationResult(None, duplicate=True, reason="near_duplicate_frame")
        self._seen.append(frame_hash)
        self._seen = self._seen[-self.max_frames :]
        bounded_frame = RedactedFrame(redacted, source_name, _iso(timestamp), frame_hash, redactions)
        readings = tuple(self._sanitize_reading(item) for item in provider.observe(bounded_frame))
        readings = tuple(item for item in readings if item is not None)
        confidence = min((item.confidence for item in readings), default=0.0)
        observation = Observation(
            observation_id=f"obs_{uuid4().hex}",
            source_name=source_name,
            capture_timestamp=_iso(timestamp),
            source_crop="redacted-frame" if redactions else "full-frame",
            readings=readings,
            provider_id=provider.provider_id,
            model_id=provider.model_id,
            confidence=confidence,
            expires_at=_iso(timestamp + timedelta(seconds=self.ttl_seconds)),
            evidence_id=f"evidence_{uuid4().hex}",
            ocr_untrusted=any(item.ocr_text and _INSTRUCTION_PATTERN.search(item.ocr_text) for item in readings),
        )
        self._observations.append(observation)
        self._observations = self._observations[-self.max_frames :]
        return ObservationResult(observation)

    def expire(self, now: datetime | None = None) -> int:
        reference = now or _now()
        before = len(self._observations)
        self._observations = [item for item in self._observations if datetime.fromisoformat(item.expires_at) > reference]
        return before - len(self._observations)

    @staticmethod
    def _sanitize_reading(reading: VisionReading) -> VisionReading | None:
        ocr, _ = sanitize_ocr(reading.ocr_text)
        return VisionReading(
            entity=reading.entity[:128],
            value=reading.value[:256],
            confidence=reading.confidence,
            source_crop=reading.source_crop[:128],
            ocr_text=ocr,
            competing_interpretations=tuple(item[:128] for item in reading.competing_interpretations[:8]),
        )
