"""Conservative resolution of visible labels to canonical game entities."""

from __future__ import annotations

from dataclasses import dataclass
import re

from .pipeline import Observation


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


@dataclass(frozen=True)
class EntityRecord:
    canonical_id: str
    title: str
    aliases: tuple[str, ...] = ()
    source_url: str | None = None
    revision: str | None = None


@dataclass(frozen=True)
class EntityMatch:
    label: str
    candidates: tuple[EntityRecord, ...]
    confidence: float
    unresolved: bool


class EntityResolver:
    def __init__(self, records: tuple[EntityRecord, ...] = ()) -> None:
        self.records = records
        self._aliases: dict[str, list[EntityRecord]] = {}
        for record in records:
            for alias in (record.title, *record.aliases):
                self._aliases.setdefault(_normalize(alias), []).append(record)

    def resolve(self, label: str, confidence: float = 0.0) -> EntityMatch:
        candidates = tuple(self._aliases.get(_normalize(label), ()))
        return EntityMatch(label, candidates, confidence, len(candidates) != 1 or confidence < 0.7)

    def resolve_observation(self, observation: Observation) -> tuple[EntityMatch, ...]:
        return tuple(self.resolve(reading.value, reading.confidence) for reading in observation.readings)


class EteyvatEntityResolver:
    """Bounded adapter over an E-Teyvat-like source; results remain data."""

    def __init__(self, source: object) -> None:
        self.source = source

    def resolve(self, label: str, confidence: float = 0.0, limit: int = 5) -> EntityMatch:
        finder = getattr(self.source, "find_entity", None)
        if not callable(finder):
            raise TypeError("knowledge source does not support entity lookup")
        results = finder(label, limit=max(1, min(5, limit)))
        records = tuple(EntityRecord(item.result_id, item.title, (label,), item.url, item.revision) for item in results)
        return EntityMatch(label, records, confidence, len(records) != 1 or confidence < 0.7)
