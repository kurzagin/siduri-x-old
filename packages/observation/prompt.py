"""Convert observations to bounded, data-only prompt material."""

from __future__ import annotations

from .pipeline import Observation


def format_observation(observation: Observation, *, max_readings: int = 16) -> str:
    readings: list[str] = []
    for reading in observation.readings[:max_readings]:
        alternatives = ", ".join(reading.competing_interpretations) or "none"
        ocr = reading.ocr_text or "none"
        readings.append(
            f"entity={reading.entity[:96]!r}; value={reading.value[:192]!r}; "
            f"confidence={reading.confidence:.2f}; alternatives={alternatives[:256]!r}; ocr_data={ocr[:256]!r}"
        )
    return (
        f"observation_id={observation.observation_id}; evidence_id={observation.evidence_id}; "
        f"source={observation.source_name[:96]!r}; provider={observation.provider_id[:96]!r}; "
        f"model={observation.model_id[:96]!r}; confidence={observation.confidence:.2f}; "
        f"expires_at={observation.expires_at}; readings=[{' | '.join(readings) or 'none'}]"
    )


def format_observations(observations: tuple[Observation, ...]) -> tuple[str, ...]:
    return tuple(format_observation(item) for item in observations)
