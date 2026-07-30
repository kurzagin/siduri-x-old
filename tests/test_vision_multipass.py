import unittest

from packages.observation.pipeline import RedactedFrame, VisionReading
from packages.vision.multipass import MultiPassVisionProvider, expand_party_list


class Pass:
    def __init__(self, value: str) -> None:
        self.value = value

    def observe(self, frame: RedactedFrame):
        return (VisionReading("test", self.value, 0.8),)


class BrokenPass:
    def observe(self, frame: RedactedFrame):
        raise RuntimeError("timeout")


class MultiPassVisionTests(unittest.TestCase):
    def test_merges_context_and_detail_readings(self) -> None:
        provider = MultiPassVisionProvider((Pass("context"), Pass("party")), provider_id="test", model_id="model")
        readings = provider.observe(RedactedFrame(b"\xff\xd8\xffdata", "fixture", "now", "hash", ()))
        self.assertEqual([item.value for item in readings], ["context", "party"])

    def test_one_failed_pass_does_not_discard_the_other(self) -> None:
        provider = MultiPassVisionProvider((BrokenPass(), Pass("detail")), provider_id="test", model_id="model")
        readings = provider.observe(RedactedFrame(b"\xff\xd8\xffdata", "fixture", "now", "hash", ()))
        self.assertEqual([item.value for item in readings], ["detail"])

    def test_grouped_party_list_derives_ordered_active_member(self) -> None:
        readings = expand_party_list((VisionReading("Party List", "Hu Tao (1), Xingqiu (2), Thoma (3), Kaedehara Kazuha (4)", 1.0),))
        self.assertEqual(readings[1].entity, "active_character")
        self.assertEqual(readings[1].value, "Hu Tao")
        self.assertEqual([item.value for item in readings[2:]], ["Hu Tao", "Xingqiu", "Thoma", "Kaedehara Kazuha"])

    def test_failed_detail_fallback_does_not_zero_valid_context_confidence(self) -> None:
        provider = MultiPassVisionProvider((Pass("context"), BrokenPass()), provider_id="test", model_id="model")
        readings = provider.observe(RedactedFrame(b"\xff\xd8\xffdata", "fixture", "now", "hash", ()))
        self.assertEqual([item.value for item in readings], ["context"])


if __name__ == "__main__":
    unittest.main()
