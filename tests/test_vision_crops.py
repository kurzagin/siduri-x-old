import unittest

from packages.observation.pipeline import RedactedFrame, VisionReading
from packages.vision.crops import CroppedVisionProvider, ImageRegion


class Provider:
    provider_id = "test"
    model_id = "model"

    def observe(self, frame):
        self.frame = frame
        return (VisionReading("party_member", "Hu Tao", 0.9),)


class CropTests(unittest.TestCase):
    def test_crop_is_in_memory_and_labels_readings(self) -> None:
        provider = Provider()
        crop = CroppedVisionProvider(provider, ImageRegion("right-party-hud", 10, 20, 30, 40), cropper=lambda frame, region: b"cropped-image")
        readings = crop.observe(RedactedFrame(b"full-image", "fixture", "now", "hash", ()))
        self.assertEqual(readings[0].source_crop, "right-party-hud")
        self.assertEqual(provider.frame.content, b"cropped-image")
        self.assertNotEqual(provider.frame.frame_hash, "hash")

    def test_top_party_member_is_derived_as_active_character(self) -> None:
        provider = CroppedVisionProvider(
            Provider(), ImageRegion("right-party-hud", 10, 20, 30, 40),
            cropper=lambda frame, region: b"cropped-image", top_party_is_active=True,
        )
        provider.provider.observe = lambda frame: (
            VisionReading("party_member", "Hu Tao", 0.99),
            VisionReading("party_member", "Xingqiu", 0.99),
        )
        readings = provider.observe(RedactedFrame(b"full-image", "fixture", "now", "hash", ()))
        self.assertEqual(readings[0].entity, "active_character")
        self.assertEqual(readings[0].value, "Hu Tao")
        self.assertEqual([item.value for item in readings[1:]], ["Hu Tao", "Xingqiu"])

    def test_regions_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            ImageRegion("bad", 0, 0, 0, 10)


if __name__ == "__main__":
    unittest.main()
