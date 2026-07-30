"""Provider-neutral multi-pass vision orchestration."""

from __future__ import annotations

import re

from packages.observation.pipeline import RedactedFrame, VisionReading


_PARTY_MEMBER_PATTERN = re.compile(r"([^,()]+?)\s*\((\d+)\)")


def expand_party_list(readings: tuple[VisionReading, ...]) -> tuple[VisionReading, ...]:
    """Expand a grouped Genshin party reading while retaining the source reading."""
    expanded: list[VisionReading] = list(readings)
    if any(item.entity == "active_character" for item in readings):
        return tuple(expanded)
    for reading in readings:
        if "party" not in reading.entity.casefold() or "list" not in reading.entity.casefold():
            continue
        numbered = [(name.strip(), int(slot)) for name, slot in _PARTY_MEMBER_PATTERN.findall(reading.value)]
        members = numbered or [(name.strip(), index) for index, name in enumerate(reading.value.split(","), start=1) if name.strip()]
        if len(members) < 2:
            continue
        members.sort(key=lambda item: item[1])
        party_readings = tuple(VisionReading(
            "party_member", name, reading.confidence, source_crop=reading.source_crop,
            ocr_text=name, competing_interpretations=reading.competing_interpretations,
        ) for name, _slot in members)
        active = VisionReading(
            "active_character", members[0][0], reading.confidence,
            source_crop=reading.source_crop, ocr_text=members[0][0],
            competing_interpretations=reading.competing_interpretations,
        )
        expanded.extend((active, *party_readings))
        break
    return tuple(expanded)


class MultiPassVisionProvider:
    """Run bounded context and detail passes over one in-memory frame."""

    def __init__(self, passes: tuple[object, ...], *, provider_id: str, model_id: str) -> None:
        if not passes:
            raise ValueError("at least one vision pass is required")
        self.passes = passes
        self.provider_id = provider_id
        self.model_id = model_id

    def observe(self, frame: RedactedFrame) -> tuple[VisionReading, ...]:
        readings: list[VisionReading] = []
        for provider in self.passes[:2]:
            try:
                result = provider.observe(frame)
            except (OSError, RuntimeError, ValueError):
                continue
            readings.extend(result[:16])
        combined = expand_party_list(tuple(readings))
        usable = tuple(item for item in combined if not (item.entity == "scene" and item.confidence == 0.0))
        return usable or combined
