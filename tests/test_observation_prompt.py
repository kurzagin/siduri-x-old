import unittest

from packages.observation.pipeline import FixtureObservationProvider, ObservationPipeline
from packages.persona.domain import MeProfile, Recipient
from packages.persona.prompt import PromptAssembler, PromptContext


class ObservationPromptTests(unittest.TestCase):
    def test_observation_prompt_is_bounded_and_evidence_linked(self) -> None:
        pipeline = ObservationPipeline()
        observation = pipeline.ingest(b"prompt-frame", source_name="genshin", provider=FixtureObservationProvider()).observation
        assert observation is not None
        me = MeProfile.from_dict({
            "identity": {"stage_name": "Fixture Kur"},
            "relationship_with_siduri": {"role": "creator"},
            "communication": {},
            "privacy": {"fields_allowed_on_stream": ["stage_name"]},
        })
        prompt = PromptAssembler(me).assemble(PromptContext(Recipient.MASTER_STREAM, "hello", observations=(observation,)))
        self.assertIn(observation.evidence_id, prompt)
        self.assertIn("ocr_data=", prompt)
        self.assertIn("[EVIDENCE / OBSERVATIONS]", prompt)
        self.assertLess(len(prompt), 10000)


if __name__ == "__main__":
    unittest.main()
