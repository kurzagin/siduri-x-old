"""Optional in-memory image crops for focused visual passes."""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass, replace
from typing import Callable

from packages.observation.pipeline import RedactedFrame, VisionReading


@dataclass(frozen=True)
class ImageRegion:
    name: str
    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if not self.name.strip() or min(self.x, self.y, self.width, self.height) < 0 or not self.width or not self.height:
            raise ValueError("image region is invalid")


def crop_image(frame: bytes, region: ImageRegion, *, timeout_seconds: float = 5.0) -> bytes:
    """Crop image bytes through ffmpeg pipes; no screenshot is written to disk."""
    command = [
        "ffmpeg", "-loglevel", "error", "-i", "pipe:0",
        "-vf", f"crop={region.width}:{region.height}:{region.x}:{region.y}",
        "-f", "image2pipe", "-vcodec", "png", "pipe:1",
    ]
    try:
        result = subprocess.run(command, input=frame, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_seconds, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as error:
        raise RuntimeError("in-memory image crop unavailable") from error
    if not result.stdout:
        raise RuntimeError("in-memory image crop was empty")
    return result.stdout


class CroppedVisionProvider:
    """Apply one in-memory crop before delegating to a vision adapter."""

    def __init__(self, provider: object, region: ImageRegion, *, cropper: Callable[[bytes, ImageRegion], bytes] = crop_image, top_party_is_active: bool = False) -> None:
        self.provider = provider
        self.region = region
        self.cropper = cropper
        self.top_party_is_active = top_party_is_active
        self.provider_id = getattr(provider, "provider_id")
        self.model_id = getattr(provider, "model_id")

    def observe(self, frame: RedactedFrame) -> tuple[VisionReading, ...]:
        cropped = self.cropper(frame.content, self.region)
        cropped_frame = RedactedFrame(
            cropped, frame.source_name, frame.capture_timestamp,
            hashlib.sha256(cropped).hexdigest(), frame.redacted_regions,
        )
        readings = tuple(replace(item, source_crop=self.region.name) for item in self.provider.observe(cropped_frame))
        if self.top_party_is_active and not any(item.entity == "active_character" for item in readings):
            party = next((item for item in readings if item.entity == "party_member"), None)
            if party is not None:
                readings = (VisionReading("active_character", party.value, party.confidence,
                                          source_crop=self.region.name, ocr_text=party.ocr_text,
                                          competing_interpretations=party.competing_interpretations), *readings)
        return readings
