"""Stable domain boundary for multimodal image providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from packages.observation.pipeline import RedactedFrame, VisionReading


@dataclass(frozen=True)
class VisionRequest:
    image: bytes
    mime_type: str
    source_ref: str
    instruction: str

    def __post_init__(self) -> None:
        if not self.image or self.mime_type not in {"image/png", "image/jpeg", "image/webp"}:
            raise ValueError("vision request requires a supported non-empty image")
        if not self.source_ref or len(self.source_ref) > 256:
            raise ValueError("vision source_ref is invalid")
        if not self.instruction.strip() or len(self.instruction) > 2000:
            raise ValueError("vision instruction is invalid")


class VisionProviderError(RuntimeError):
    pass


class VisionProvider(Protocol):
    provider_id: str
    model_id: str

    def analyze(self, request: VisionRequest) -> tuple[VisionReading, ...]: ...


def request_from_frame(frame: RedactedFrame, instruction: str) -> VisionRequest:
    content = frame.content
    if content.startswith(b"\x89PNG"):
        mime = "image/png"
    elif content.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif content.startswith(b"RIFF") and b"WEBP" in content[:16]:
        mime = "image/webp"
    else:
        raise VisionProviderError("frame format is not a supported image")
    return VisionRequest(content, mime, f"{frame.source_name}:{frame.frame_hash}", instruction)


class VisionObservationAdapter:
    """Adapt a request-based vision provider to the observation pipeline."""

    def __init__(self, provider: VisionProvider, instruction: str) -> None:
        self.provider = provider
        self.provider_id = provider.provider_id
        self.model_id = provider.model_id
        self.instruction = instruction

    def observe(self, frame: RedactedFrame) -> tuple[VisionReading, ...]:
        return self.provider.analyze(request_from_frame(frame, self.instruction))
