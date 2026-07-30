import unittest
from datetime import datetime, timedelta, timezone

from packages.observation.grounding import current_observations, resolve_visible_labels
from packages.observation.pipeline import ObservationPipeline, VisionReading, RedactedFrame


class Result:
    result_id = "eteyvat:paimon"
    title = "Paimon"
    url = "https://eteyvat.example/paimon"
    revision = "rev-1"
    preview = True


class Source:
    base_url = "https://eteyvat.example"
    revision = "rev-1"

    def __init__(self) -> None:
        self.labels: list[str] = []

    def find_entity(self, label: str, limit: int):
        self.labels.append(label)
        return [Result()] if label == "Paimon" else []


class GroundingTests(unittest.TestCase):
    def test_resolution_preserves_citation_and_unresolved_label(self) -> None:
        pipeline = ObservationPipeline()

        class Provider:
            provider_id = "test-vision"
            model_id = "test-model"

            def observe(self, frame: RedactedFrame):
                return (VisionReading("character", "Paimon", 0.9), VisionReading("label", "Unknown UI", 0.8))

        observation = pipeline.ingest(b"grounding-frame", source_name="genshin", provider=Provider()).observation
        assert observation is not None
        source = Source()
        grounded = resolve_visible_labels(observation, source)
        self.assertIn("eteyvat:paimon", [item["evidence_id"] for item in grounded.citations])
        self.assertTrue(any("Unknown UI" in item[0] for item in grounded.prompt_items))
        self.assertTrue(grounded.citations[0]["preview"])

    def test_resolution_has_a_total_label_lookup_bound(self) -> None:
        class ManyReadingProvider:
            provider_id = "test-vision"
            model_id = "test-model"

            def observe(self, frame: RedactedFrame):
                return tuple(VisionReading("label", f"label-{index}", 0.5) for index in range(10))

        pipeline = ObservationPipeline()
        observation = pipeline.ingest(b"many-label-frame", source_name="genshin", provider=ManyReadingProvider()).observation
        assert observation is not None
        source = Source()
        resolve_visible_labels(observation, source)
        self.assertEqual(len(source.labels), 3)

    def test_current_observations_excludes_expired_items(self) -> None:
        pipeline = ObservationPipeline(ttl_seconds=1)
        observation = pipeline.ingest(b"expiry-frame", source_name="genshin", provider=SourceProvider()).observation
        assert observation is not None
        now = datetime.now(timezone.utc) + timedelta(seconds=2)
        self.assertEqual(current_observations(pipeline, now), ())


class SourceProvider:
    provider_id = "test-vision"
    model_id = "test-model"

    def observe(self, frame: RedactedFrame):
        return (VisionReading("screen", "scene", 0.5),)


if __name__ == "__main__":
    unittest.main()
