import unittest

from packages.observation.pipeline import RedactedFrame, VisionReading
from packages.vision.contract import VisionObservationAdapter


class Provider:
    provider_id = "test-vision"
    model_id = "test-model"

    def analyze(self, request):
        self.request = request
        return (VisionReading("screen", "exploration", 0.8),)


class VisionAdapterTests(unittest.TestCase):
    def test_adapter_connects_provider_contract_to_observation_contract(self) -> None:
        provider = Provider()
        adapter = VisionObservationAdapter(provider, "visible evidence only")
        result = adapter.observe(RedactedFrame(b"\xff\xd8\xffdata", "fixture", "now", "hash", ()))
        self.assertEqual(result[0].value, "exploration")
        self.assertEqual(provider.request.mime_type, "image/jpeg")


if __name__ == "__main__":
    unittest.main()
