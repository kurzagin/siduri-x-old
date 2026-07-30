import unittest

from packages.observation.aggregate import TemporalObservationAggregator
from packages.observation.pipeline import ObservationPipeline, RedactedFrame, VisionReading
from packages.observation.resolve import EntityRecord, EntityResolver


class ObservationReasoningTests(unittest.TestCase):
    def test_ambiguous_or_low_confidence_entity_stays_unresolved(self) -> None:
        resolver = EntityResolver((EntityRecord("a", "Traveler", ("Aether",)), EntityRecord("b", "Traveler", ("Lumine",))))
        match = resolver.resolve("Traveler", 0.95)
        self.assertTrue(match.unresolved)
        self.assertEqual(len(match.candidates), 2)

    def test_low_confidence_exact_match_stays_unresolved(self) -> None:
        resolver = EntityResolver((EntityRecord("a", "Paimon"),))
        self.assertTrue(resolver.resolve("Paimon", 0.6).unresolved)

    def test_temporal_aggregation_preserves_conflict(self) -> None:
        class ConflictingProvider:
            provider_id = "test"
            model_id = "test"
            value = "one"

            def observe(self, frame: RedactedFrame) -> tuple[VisionReading, ...]:
                value = self.value
                self.value = "two"
                return (VisionReading("screen", value, 0.8),)

        pipeline = ObservationPipeline()
        provider = ConflictingProvider()
        first = pipeline.ingest(b"first", source_name="fixture", provider=provider).observation
        second = pipeline.ingest(b"second", source_name="fixture", provider=provider).observation
        assert first is not None and second is not None
        aggregate = TemporalObservationAggregator().aggregate((first, second))
        self.assertEqual(aggregate[0].values, ("one", "two"))
        self.assertTrue(aggregate[0].conflicting)


if __name__ == "__main__":
    unittest.main()
