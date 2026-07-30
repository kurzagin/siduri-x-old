from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count
from queue import PriorityQueue
from typing import Callable


@dataclass(order=True)
class SpeechJob:
    sort_key: tuple[int, int] = field(init=False)
    priority: int
    job_id: str = field(compare=False)
    speak: Callable[[], object] = field(compare=False)
    interruptible: bool = field(default=True, compare=False)
    _sequence: int = field(default=0, compare=False, repr=False)

    def __post_init__(self) -> None:
        self.sort_key = (-self.priority, self._sequence)


class SpeechQueue:
    def __init__(self) -> None:
        self._items: PriorityQueue[SpeechJob] = PriorityQueue()
        self._sequence = count()
        self._cancelled: set[str] = set()

    def enqueue(self, job_id: str, priority: int, speak: Callable[[], object], interruptible: bool = True) -> None:
        if not job_id or not 0 <= priority <= 100:
            raise ValueError("job_id and priority are invalid")
        self._items.put(SpeechJob(priority, job_id, speak, interruptible, next(self._sequence)))

    def cancel(self, job_id: str) -> None:
        self._cancelled.add(job_id)

    def run_next(self) -> object | None:
        while not self._items.empty():
            job = self._items.get()
            if job.job_id in self._cancelled:
                self._cancelled.discard(job.job_id)
                continue
            return job.speak()
        return None

    def __len__(self) -> int:
        return self._items.qsize()
