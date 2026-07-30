"""Short-lived aggregation that preserves uncertainty and conflicts."""

from __future__ import annotations

from dataclasses import dataclass

from .pipeline import Observation


@dataclass(frozen=True)
class AggregatedReading:
    entity: str
    values: tuple[str, ...]
    confidence: float
    conflicting: bool
    evidence_ids: tuple[str, ...]


class TemporalObservationAggregator:
    def aggregate(self, observations: tuple[Observation, ...]) -> tuple[AggregatedReading, ...]:
        grouped: dict[str, list[tuple[str, float, str]]] = {}
        for observation in observations:
            for reading in observation.readings:
                grouped.setdefault(reading.entity, []).append((reading.value, reading.confidence, observation.evidence_id))
        result: list[AggregatedReading] = []
        for entity, readings in grouped.items():
            values = tuple(dict.fromkeys(item[0] for item in readings))
            result.append(AggregatedReading(entity, values, min(item[1] for item in readings),
                                            len(values) > 1, tuple(dict.fromkeys(item[2] for item in readings))))
        return tuple(result)
