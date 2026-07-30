from __future__ import annotations

import unittest

from apps.orchestrator.src.siduri_orchestrator.contracts import ResponsePlan
from packages.config.providers import ProviderConfig
from packages.model_router.router import GenerationRequest, ModelRouter, RateLimitProviderFailure
from packages.model_router.telemetry import TelemetryRecorder


class Prompt03Tests(unittest.TestCase):
    def test_provider_config_rejects_insecure_remote_endpoint(self) -> None:
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            ProviderConfig("zai", "glm-5.2", "http://remote.example/api", frozenset({"structured_generation"})).validate()

    def test_retry_and_telemetry_never_include_prompt(self) -> None:
        telemetry = TelemetryRecorder()

        class Flaky:
            provider_id = "flaky"
            model_id = "test"
            capabilities = frozenset({"structured_generation"})
            calls = 0

            def generate_response(self, _request: GenerationRequest) -> ResponsePlan:
                self.calls += 1
                if self.calls == 1:
                    raise RateLimitProviderFailure("limited")
                return ResponsePlan("master_stream", "test", "summary", "確認済み", "Confirmed", "Terkonfirmasi")

        response = ModelRouter((Flaky(),), telemetry=telemetry).generate(GenerationRequest("test", "PRIVATE PROMPT", recipient="master_stream"))
        self.assertEqual(response.recipient, "master_stream")
        serialized = repr(telemetry.events)
        self.assertNotIn("PRIVATE PROMPT", serialized)
        self.assertTrue(any(event["event_type"] == "retry_succeeded" for event in telemetry.events))

    def test_recipient_mismatch_isolated_and_degraded(self) -> None:
        class Misaddressed:
            provider_id = "misaddressed"
            model_id = "test"
            capabilities = frozenset({"structured_generation"})

            def generate_response(self, _request: GenerationRequest) -> ResponsePlan:
                return ResponsePlan("viewer_direct", "test", "bad", "危険", "Unsafe", "Tidak aman")

        result = ModelRouter((Misaddressed(),), failure_threshold=1).generate(GenerationRequest("test", "data", recipient="master_stream"))
        self.assertEqual(result.intent, "degraded_mode")
        self.assertNotEqual(result.recipient, "viewer_direct")


if __name__ == "__main__":
    unittest.main()
