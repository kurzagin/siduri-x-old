"""Application service joining OBS capture with bounded observations."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable

from packages.obs.capture import ObsCaptureBoundary

from .pipeline import Observation, ObservationPipeline, ObservationProvider


@dataclass(frozen=True)
class ObserveNowResult:
    observation: Observation | None
    capture_reason: str | None = None
    duplicate: bool = False


class ObservationService:
    def __init__(self, capture: ObsCaptureBoundary, pipeline: ObservationPipeline,
                 provider: ObservationProvider, redactor: Callable[[bytes], bytes] | None = None) -> None:
        self.capture = capture
        self.pipeline = pipeline
        self.provider = provider
        self.redactor = redactor

    def observe_now(self) -> ObserveNowResult:
        captured = self.capture.capture_once()
        if captured.frame is None:
            return ObserveNowResult(None, capture_reason=captured.reason)
        frame = self.redactor(captured.frame) if self.redactor else captured.frame
        try:
            result = self.pipeline.ingest(frame, source_name=captured.source_name,
                                          provider=self.provider)
        except (OSError, RuntimeError, ValueError):
            # Provider output and transport failures must not tear down the
            # operator HTTP request or expose provider-specific details.
            return ObserveNowResult(None, capture_reason="vision_failed")
        return ObserveNowResult(result.observation, capture_reason=result.reason, duplicate=result.duplicate)
