import unittest

from packages.memory.teaching import extract_explicit_teaching


class ExplicitTeachingTests(unittest.TestCase):
    def test_relationship_and_behavior_are_orthogonal(self) -> None:
        extraction = extract_explicit_teaching("Call me Master in private")
        self.assertEqual(len(extraction.claims), 1)
        self.assertEqual(extraction.claims[0]["claim_type"], "relationship")
        self.assertEqual(extraction.claims[0]["predicate"], "preferred_address")
        self.assertEqual(len(extraction.runtime_effects), 1)
        self.assertEqual(extraction.runtime_effects[0]["knowledge_domain"], "relationship")
        self.assertEqual(extraction.runtime_effects[0]["runtime_effect"], "behavioral_rule")
        self.assertEqual(extraction.runtime_effects[0]["scope"]["audiences"], ["master_private"])

    def test_game_account_fields_are_atomic_private_claims(self) -> None:
        extraction = extract_explicit_teaching("My Genshin UID is 123456789")
        self.assertEqual(extraction.runtime_effects, ())
        self.assertEqual(extraction.claims[0]["subject"], "primary_user.genshin_account")
        self.assertEqual(extraction.claims[0]["predicate"], "uid")
        self.assertEqual(extraction.claims[0]["value"], "123456789")
        self.assertEqual(extraction.claims[0]["sensitivity"], "private")

    def test_ordinary_conversation_does_not_create_candidates(self) -> None:
        extraction = extract_explicit_teaching("That battle was fun today")
        self.assertEqual(extraction.claims, ())
        self.assertEqual(extraction.runtime_effects, ())

    def test_one_teaching_message_decomposes_multiple_atomic_claims(self) -> None:
        extraction = extract_explicit_teaching(
            "Your name is Siduri and I am your creator. My Genshin UID is 123456789 and my Genshin server is Asia."
        )
        values = {(claim["subject"], claim["predicate"]): claim["value"] for claim in extraction.claims}
        self.assertEqual(values[("siduri", "name")], "Siduri")
        self.assertEqual(values[("primary_user", "relationship_to_siduri")], "creator")
        self.assertEqual(values[("primary_user.genshin_account", "uid")], "123456789")
        self.assertEqual(values[("primary_user.genshin_account", "server")], "Asia")

if __name__ == "__main__":
    unittest.main()
