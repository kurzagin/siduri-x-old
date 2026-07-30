from datetime import datetime, timedelta, timezone
import unittest

from packages.observation.trigger import FrameTrigger


class ObservationTriggerTests(unittest.TestCase):
    def test_suppresses_duplicate_and_fast_frames(self) -> None:
        trigger = FrameTrigger(min_interval_seconds=2)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.assertTrue(trigger.should_capture(b"a", now=start))
        self.assertFalse(trigger.should_capture(b"a", now=start + timedelta(seconds=3)))
        self.assertFalse(trigger.should_capture(b"b", now=start + timedelta(seconds=1)))
        self.assertTrue(trigger.should_capture(b"b", now=start + timedelta(seconds=3)))

    def test_enforces_rolling_budget(self) -> None:
        trigger = FrameTrigger(min_interval_seconds=0, max_captures_per_minute=2)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.assertTrue(trigger.should_capture(b"a", now=start))
        self.assertTrue(trigger.should_capture(b"b", now=start + timedelta(seconds=1)))
        self.assertFalse(trigger.should_capture(b"c", now=start + timedelta(seconds=2)))
        self.assertTrue(trigger.should_capture(b"c", now=start + timedelta(minutes=1, seconds=1)))


if __name__ == "__main__":
    unittest.main()
