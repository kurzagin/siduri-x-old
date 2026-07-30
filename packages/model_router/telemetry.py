from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from time import monotonic
from typing import Any


@dataclass
class TelemetryRecorder:
    """Small process-local recorder; fields are deliberately metadata-only."""
    events: list[dict[str, Any]] = field(default_factory=list)
    path: Path | None = None

    def __post_init__(self) -> None:
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event_type: str, **fields: Any) -> None:
        safe = {key: value for key, value in fields.items() if key not in {"prompt", "api_key", "content", "raw_text"}}
        event = {"event_type": event_type, **safe}
        self.events.append(event)
        if self.path:
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, ensure_ascii=False) + "\n")

    def timer(self) -> float:
        return monotonic()
