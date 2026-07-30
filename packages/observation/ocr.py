"""Bounded OCR contract; OCR output is data, never instructions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .pipeline import RedactedFrame, sanitize_ocr


@dataclass(frozen=True)
class OCRFragment:
    text: str
    crop: str
    confidence: float
    instruction_shaped: bool = False


class OCRProvider(Protocol):
    provider_id: str
    model_id: str

    def read(self, frame: RedactedFrame) -> tuple[OCRFragment, ...]: ...


class FixtureOCRProvider:
    provider_id = "fixture-ocr"
    model_id = "fixture-v1"

    def read(self, frame: RedactedFrame) -> tuple[OCRFragment, ...]:
        return (OCRFragment("Synthetic OCR fixture; no live text", frame.source_name, 0.0),)


def sanitize_fragments(fragments: tuple[OCRFragment, ...], limit: int = 32) -> tuple[OCRFragment, ...]:
    sanitized: list[OCRFragment] = []
    for fragment in fragments[:limit]:
        text, shaped = sanitize_ocr(fragment.text)
        if text:
            sanitized.append(OCRFragment(text, fragment.crop[:128], max(0.0, min(1.0, fragment.confidence)), shaped))
    return tuple(sanitized)
