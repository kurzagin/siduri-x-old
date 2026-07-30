"""Bounded automatic observation trigger policy."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, timezone
import hashlib


class FrameTrigger:
    def __init__(self, *, min_interval_seconds: float = 2.0, max_captures_per_minute: int = 12) -> None:
        if min_interval_seconds < 0 or max_captures_per_minute <= 0:
            raise ValueError("trigger limits are invalid")
        self.min_interval = timedelta(seconds=min_interval_seconds)
        self.max_captures = max_captures_per_minute
        self._last_capture: datetime | None = None
        self._recent: deque[datetime] = deque()
        self._last_hash: str | None = None

    def should_capture(self, frame: bytes, *, now: datetime | None = None) -> bool:
        if not frame:
            return False
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        while self._recent and self._recent[0] <= current - timedelta(minutes=1):
            self._recent.popleft()
        digest = hashlib.sha256(frame).hexdigest()
        if digest == self._last_hash:
            return False
        if self._last_capture is not None and current - self._last_capture < self.min_interval:
            return False
        if len(self._recent) >= self.max_captures:
            return False
        self._last_hash = digest
        self._last_capture = current
        self._recent.append(current)
        return True

    def reset(self) -> None:
        self._last_capture = None
        self._recent.clear()
        self._last_hash = None
