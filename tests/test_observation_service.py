import unittest

from packages.observation.pipeline import FixtureObservationProvider, ObservationPipeline
from packages.observation.service import ObservationService
from packages.obs.capture import FakeObsTransport, ObsCaptureBoundary


class ObservationServiceTests(unittest.TestCase):
    def test_observe_now_does_not_expose_raw_frame(self) -> None:
        capture = ObsCaptureBoundary(FakeObsTransport(b"private-test-frame"), source_name="genshin", enabled=True)
        result = ObservationService(capture, ObservationPipeline(), FixtureObservationProvider()).observe_now()
        self.assertIsNotNone(result.observation)
        self.assertNotIn("private-test-frame", str(result.observation.to_dict()))

    def test_observe_now_reports_disabled_capture(self) -> None:
        capture = ObsCaptureBoundary(FakeObsTransport(), source_name="genshin", enabled=False)
        result = ObservationService(capture, ObservationPipeline(), FixtureObservationProvider()).observe_now()
        self.assertIsNone(result.observation)
        self.assertEqual(result.capture_reason, "capture_disabled")

    def test_observe_now_applies_in_memory_redactor_before_provider(self) -> None:
        seen: list[bytes] = []

        class Provider:
            provider_id = "test"
            model_id = "test"

            def observe(self, frame):
                seen.append(frame.content)
                return ()

        capture = ObsCaptureBoundary(FakeObsTransport(b"raw"), source_name="genshin", enabled=True)
        result = ObservationService(capture, ObservationPipeline(), Provider(), lambda value: value.replace(b"raw", b"safe")).observe_now()
        self.assertIsNotNone(result.observation)
        self.assertEqual(seen, [b"safe"])


if __name__ == "__main__":
    unittest.main()
