"""Bounded grounding of live observations against trusted knowledge."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re

from packages.knowledge.eteyvat import EteyvatError

from .pipeline import Observation
from .resolve import EteyvatEntityResolver, EntityMatch


@dataclass(frozen=True)
class GroundedKnowledge:
    """Prompt material and operator citation metadata for one response."""

    prompt_items: tuple[tuple[str, str, str, str | None], ...]
    citations: tuple[dict[str, object], ...]
    matches: tuple[EntityMatch, ...]


def current_observations(pipeline: object, now: datetime | None = None) -> tuple[Observation, ...]:
    """Expire retained observations before returning the only usable evidence."""
    reference = now or datetime.now(timezone.utc)
    expire = getattr(pipeline, "expire")
    expire(reference)
    return tuple(getattr(pipeline, "observations"))


def _knowledge_query(reading_entity: str, label: str) -> str:
    """Strip quest-action/count wording before an entity lookup."""
    if "quest" in reading_entity.casefold():
        match = re.search(r"(?:defeat|obtain|collect|protect)\s+(.+?)(?:\s+\d+\s*/\s*\d+)?$", label, re.IGNORECASE)
        if match:
            label = match.group(1).strip()
            if label.casefold().endswith("s") and not label.casefold().endswith("ss"):
                label = label[:-1]
    return label[:200]


def resolve_visible_labels(observation: Observation, source: object, *, max_labels: int = 3) -> GroundedKnowledge:
    """Resolve a bounded set of visible values, retaining unresolved labels as data."""
    resolver = EteyvatEntityResolver(source)
    prompt_items: list[tuple[str, str, str, str | None]] = []
    citations: list[dict[str, object]] = []
    matches: list[EntityMatch] = []
    labels: list[tuple[str, str]] = []
    priority = {
        "active_character": 0,
        "party_member": 1,
        "quest objective": 2,
        "enemy": 3,
        "location": 4,
    }
    readings = sorted(observation.readings, key=lambda item: priority.get(item.entity.casefold().replace("_", " "), 10))
    for reading in readings:
        if reading.entity == "scene" and reading.confidence == 0.0:
            continue
        label = reading.value.strip()[:200]
        query = _knowledge_query(reading.entity, label)
        if label and all(existing != label for existing, _query in labels):
            labels.append((label, query))
        if len(labels) >= max(1, min(3, max_labels)):
            break
    for label, query in labels:
        try:
            resolved = resolver.resolve(query, confidence=next((item.confidence for item in observation.readings if item.value.strip() == label), 0.0), limit=3)
            match = EntityMatch(label, resolved.candidates, resolved.confidence, resolved.unresolved)
        except (EteyvatError, OSError, RuntimeError, TypeError, ValueError):
            match = EntityMatch(label, (), 0.0, True)
        matches.append(match)
        if not match.candidates:
            prompt_items.append((f"Unresolved visible label: {label}", "No bounded E-Teyvat entity match was confirmed; preserve this uncertainty.", source.base_url, getattr(source, "revision", None)))
            continue
        for candidate in match.candidates[:3]:
            prompt_items.append((candidate.title, f"Visible label {label!r}; candidate data remains uncertain: {candidate.canonical_id}.", candidate.source_url or source.base_url, candidate.revision))
            citations.append({
                "evidence_id": candidate.canonical_id,
                "label": label,
                "title": candidate.title,
                "url": candidate.source_url or source.base_url,
                "revision": candidate.revision,
                "preview": candidate.preview,
                "resolved": not match.unresolved,
            })
    return GroundedKnowledge(tuple(prompt_items), tuple(citations), tuple(matches))
