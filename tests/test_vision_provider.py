from pathlib import Path
import unittest

from packages.observation.pipeline import RedactedFrame
from packages.vision.contract import request_from_frame
from packages.vision.fixtures import load_asset_images
from packages.vision.zai_glm5v import ZaiGlm5VisionProvider


class Transport:
    def __init__(self) -> None:
        self.request: dict[str, str] = {}

    def complete(self, *, model: str, instruction: str, image_data_url: str) -> object:
        self.request = {"model": model, "instruction": instruction, "image_data_url": image_data_url}
        return {"readings": [{"entity": "screen", "value": "exploration", "confidence": 0.8}]}


class StateTransport(Transport):
    def complete(self, *, model: str, instruction: str, image_data_url: str) -> object:
        return {"readings": [{"character_active": "Keqing", "game_state": "exploration", "current_hp": 60}]}


class VisionProviderTests(unittest.TestCase):
    def test_assets_detect_jpeg_by_signature_not_extension(self) -> None:
        assets = load_asset_images(Path(__file__).parents[1] / "assets")
        self.assertEqual(len(assets), 3)
        self.assertTrue(all(item.mime_type == "image/jpeg" for item in assets))

    def test_zai_adapter_normalizes_response_without_domain_coupling(self) -> None:
        transport = Transport()
        provider = ZaiGlm5VisionProvider(transport)
        frame = RedactedFrame(b"\xff\xd8\xfffixture", "fixture", "2026-01-01T00:00:00+00:00", "hash", ())
        readings = provider.analyze(request_from_frame(frame, "Return only normalized visual observations."))
        self.assertEqual(provider.model_id, "glm-5v-turbo")
        self.assertEqual(readings[0].value, "exploration")
        self.assertTrue(transport.request["image_data_url"].startswith("data:image/jpeg;base64,"))

    def test_zai_adapter_preserves_keyed_state_response(self) -> None:
        provider = ZaiGlm5VisionProvider(StateTransport())
        frame = RedactedFrame(b"\xff\xd8\xfffixture", "fixture", "2026-01-01T00:00:00+00:00", "hash", ())
        readings = provider.analyze(request_from_frame(frame, "Return visible state."))
        self.assertEqual([item.entity for item in readings], ["character_active", "game_state", "current_hp"])


if __name__ == "__main__":
    unittest.main()
