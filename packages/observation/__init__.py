"""Fixture-first, privacy-aware observation boundary."""

from .pipeline import (
    ByteRegion,
    Observation,
    ObservationPipeline,
    ObservationProvider,
    ObservationResult,
    RedactedFrame,
    FixtureObservationProvider,
    VisionReading,
)
from .service import ObservationService, ObserveNowResult
from .resolve import EntityMatch, EntityRecord, EntityResolver, EteyvatEntityResolver
from .aggregate import AggregatedReading, TemporalObservationAggregator
from .png import PixelRect, redact_png
from .ocr import FixtureOCRProvider, OCRFragment, OCRProvider, sanitize_fragments
from .trigger import FrameTrigger

__all__ = [
    "ByteRegion",
    "Observation",
    "ObservationPipeline",
    "ObservationProvider",
    "ObservationResult",
    "RedactedFrame",
    "FixtureObservationProvider",
    "VisionReading",
    "ObservationService",
    "ObserveNowResult",
    "EntityMatch",
    "EntityRecord",
    "EntityResolver",
    "EteyvatEntityResolver",
    "AggregatedReading",
    "TemporalObservationAggregator",
    "PixelRect",
    "redact_png",
    "FixtureOCRProvider",
    "OCRFragment",
    "OCRProvider",
    "sanitize_fragments",
    "FrameTrigger",
]
