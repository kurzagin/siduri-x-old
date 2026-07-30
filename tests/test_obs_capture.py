import unittest

from packages.obs.capture import FakeObsTransport, ObsCaptureBoundary


class ObsCaptureTests(unittest.TestCase):
    def test_kill_switch_prevents_transport_capture(self) -> None:
        transport = FakeObsTransport()
        boundary = ObsCaptureBoundary(transport, source_name="Genshin Game", enabled=False)
        result = boundary.capture_once()
        self.assertIsNone(result.frame)
        self.assertEqual(result.reason, "capture_disabled")
        self.assertEqual(transport.requests, [])

    def test_capture_uses_explicit_source_and_reports_status(self) -> None:
        transport = FakeObsTransport(streaming=True)
        boundary = ObsCaptureBoundary(transport, source_name="Fixture Game", enabled=True)
        result = boundary.capture_once()
        self.assertEqual(result.frame, b"fixture-frame")
        self.assertEqual(transport.requests, ["Fixture Game"])
        self.assertTrue(result.status.streaming)
        self.assertTrue(result.status.capture_enabled)

    def test_disconnect_is_safe(self) -> None:
        transport = FakeObsTransport(connected=False)
        boundary = ObsCaptureBoundary(transport, source_name="Fixture", enabled=True)
        result = boundary.capture_once()
        self.assertIsNone(result.frame)
        self.assertEqual(result.reason, "obs_disconnected")

    def test_enable_is_explicit(self) -> None:
        transport = FakeObsTransport()
        boundary = ObsCaptureBoundary(transport, source_name="Fixture")
        status = boundary.set_enabled(True)
        self.assertTrue(status.capture_enabled)
        self.assertEqual(boundary.capture_once().frame, b"fixture-frame")


if __name__ == "__main__":
    unittest.main()
