import unittest
from unittest.mock import patch
from dataclasses import dataclass

from apps.orchestrator.src.siduri_orchestrator import server
from packages.model_router.router import MockStructuredProvider, ModelRouter
from packages.memory.service import MemoryService
from apps.orchestrator.src.siduri_orchestrator.contracts import ResponsePlan


class ChatTests(unittest.TestCase):
    def test_private_chat_uses_private_recipient_without_public_broadcast(self) -> None:
        router = ModelRouter((MockStructuredProvider(),))
        with patch.object(server, "ROUTER", router):
            plan, metadata = server.private_chat_response({"message": "Hello, Siduri", "history": []})
        self.assertEqual(plan.recipient, "master_private")
        self.assertFalse(plan.requires_operator_approval)
        self.assertEqual(metadata["channel"], "private_chat")

    def test_empty_memory_does_not_predeclare_user_relationship(self) -> None:
        class NoKnowledge:
            source_id = "none"
            revision = "none"

            def search(self, _query: str, limit: int):
                return []

            def find_entity(self, _subject: str, limit: int):
                return []

        class CapturingProvider(MockStructuredProvider):
            def generate_response(self, request):
                self.request = request
                return super().generate_response(request)

        memory = MemoryService()
        provider = CapturingProvider()
        with (
            patch.object(server, "MEMORY", memory),
            patch.object(server, "ETEYVAT", NoKnowledge()),
            patch.object(server, "ROUTER", ModelRouter((provider,))),
        ):
            server.private_chat_response({"message": "Hey", "history": []})

        self.assertIn("PRIVATE PRIMARY-USER REQUEST", provider.request.prompt)
        self.assertNotIn("DIRECT CREATOR REQUEST", provider.request.prompt)
        self.assertIn("do not claim prior personal knowledge", provider.request.system_prompt)
        self.assertNotIn("Address the primary user as", provider.request.system_prompt)

    def test_chat_history_is_bounded_and_validated(self) -> None:
        with self.assertRaises(ValueError):
            server.private_chat_response({"message": "hello", "history": [{"role": "system", "content": "bad"}]})

    def test_private_chat_calls_eteyvat_and_attaches_knowledge_evidence(self) -> None:
        @dataclass(frozen=True)
        class Result:
            result_id: str = "eteyvat:entity:41"
            title: str = "Hu Tao"
            content: str = "Hu Tao is a Pyro character."
            url: str = "https://eteyvat.example/hu-tao"
            revision: str = "rev-test"
            preview: bool = False

        class Knowledge:
            source_id = "eteyvat"
            revision = "rev-test"

            def __init__(self) -> None:
                self.queries: list[str] = []

            def search(self, query: str, limit: int):
                self.queries.append(query)
                return [Result()]

        class CapturingProvider(MockStructuredProvider):
            def generate_response(self, request):
                self.request = request
                return super().generate_response(request)

        knowledge = Knowledge()
        provider = CapturingProvider()
        with patch.object(server, "ETEYVAT", knowledge), patch.object(server, "ROUTER", ModelRouter((provider,))):
            plan, metadata = server.private_chat_response({"message": "Tell me about Hu Tao", "history": []})
        self.assertEqual(knowledge.queries, ["Tell me about Hu Tao"])
        self.assertIn("eteyvat:entity:41", plan.evidence_ids)
        self.assertEqual(metadata["citations"][0]["title"], "Hu Tao")
        self.assertIn("Hu Tao is a Pyro character", provider.request.prompt)

    def test_self_identity_chat_does_not_query_eteyvat_or_attach_citations(self) -> None:
        class Knowledge:
            source_id = "eteyvat"
            revision = "rev-test"

            def __init__(self) -> None:
                self.calls = 0

            def search(self, _query: str, limit: int):
                self.calls += 1
                return []

            def find_entity(self, _subject: str, limit: int):
                self.calls += 1
                return []

        knowledge = Knowledge()
        with patch.object(server, "ETEYVAT", knowledge):
            plan, metadata = server.private_chat_response({"message": "hey, who are you??", "history": []})

        self.assertEqual(knowledge.calls, 0)
        self.assertEqual(plan.evidence_ids, ())
        self.assertEqual(metadata["citations"], [])
        self.assertIsNone(metadata["knowledge_source"])

    def test_chat_candidates_are_pending_until_review(self) -> None:
        class CandidateProvider(MockStructuredProvider):
            def generate_response(self, request):
                return ResponsePlan(
                    recipient="master_private", intent="private_chat", semantic_summary="candidate",
                    spoken_ja="候補です。", subtitle_en="Candidate.", subtitle_id="Kandidat.",
                    memory_proposals=({"content": "Kur prefers calm, concise conversation.", "provenance": "siduri_private_chat", "sensitivity": "private", "allowed_audiences": ["master_private"]},),
                )

        with patch.object(server, "ROUTER", ModelRouter((CandidateProvider(),))):
            _plan, metadata = server.private_chat_response({"message": "I prefer calm, concise conversation.", "history": []})
        proposals = metadata["memory_proposals"]
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["status"], "pending")
        self.assertNotIn(proposals[0]["proposal_id"], [item.memory_id for item in server.MEMORY.list()])

    def test_deterministic_behavior_wins_over_model_miscategorization(self) -> None:
        class MiscategorizingProvider(MockStructuredProvider):
            def generate_response(self, request):
                return ResponsePlan(
                    recipient="master_private", intent="private_chat", semantic_summary="candidate",
                    spoken_ja="了解です。", subtitle_en="Understood.", subtitle_id="Dipahami.",
                    behavioral_proposals=({
                        "memory_class": "identity",
                        "runtime_effect": "identity_context",
                        "knowledge_domain": "identity",
                        "domain": "identity",
                        "subject": "master_private",
                        "predicate": "preferred_address_private",
                        "value": "Captain-Test",
                        "activation": "always",
                        "scope": {"recipient_ids": [], "audiences": [], "session_modes": []},
                        "behavior": {"instruction": "", "frequency": "contextual", "preferred_positions": []},
                    },),
                )

        memory = MemoryService()
        with patch.object(server, "MEMORY", memory), patch.object(server, "ROUTER", ModelRouter((MiscategorizingProvider(),))):
            _plan, metadata = server.private_chat_response({"message": "Call me Captain-Test in private", "history": []})

        self.assertEqual(len(metadata["behavioral_proposals"]), 1)
        self.assertEqual(metadata["behavioral_proposals"][0]["memory_class"], "behavioral")
        self.assertEqual(metadata["behavioral_proposals"][0]["domain"], "relationship")

    def test_confirmed_private_address_is_sent_in_provider_system_prompt(self) -> None:
        class Knowledge:
            source_id = "eteyvat"
            revision = "test"

            def search(self, _query: str, limit: int):
                return []

            def find_entity(self, _subject: str, limit: int):
                return []

        class CapturingProvider(MockStructuredProvider):
            def generate_response(self, request):
                self.request = request
                return super().generate_response(request)

        memory = MemoryService()
        provider = CapturingProvider()
        with (
            patch.object(server, "MEMORY", memory),
            patch.object(server, "ETEYVAT", Knowledge()),
            patch.object(server, "ROUTER", ModelRouter((provider,))),
        ):
            _plan, metadata = server.private_chat_response({"message": "Call me Master in private", "history": []})
            self.assertEqual(len(metadata["memory_proposals"]), 1)
            self.assertEqual(len(metadata["behavioral_proposals"]), 1)
            memory.approve(metadata["memory_proposals"][0]["proposal_id"])
            memory.approve_behavioral_directive(metadata["behavioral_proposals"][0]["directive_id"])

            server.private_chat_response({"message": "How was your day?", "history": []})

        self.assertIn("Address the primary user as Master in private conversations.", provider.request.system_prompt)
        self.assertNotIn("Address the primary user as Master in private conversations.", provider.request.prompt)

    def test_game_uid_uses_normal_approved_memory_flow(self) -> None:
        class Knowledge:
            source_id = "eteyvat"
            revision = "test"

            def __init__(self) -> None:
                self.calls = 0

            def search(self, _query: str, limit: int):
                self.calls += 1
                return []

            def find_entity(self, _subject: str, limit: int):
                self.calls += 1
                return []

        class CapturingProvider(MockStructuredProvider):
            def __init__(self) -> None:
                self.requests = []

            def generate_response(self, request):
                self.requests.append(request)
                return super().generate_response(request)

        uid = "123456789"
        memory = MemoryService()
        knowledge = Knowledge()
        provider = CapturingProvider()
        with (
            patch.object(server, "MEMORY", memory),
            patch.object(server, "ETEYVAT", knowledge),
            patch.object(server, "ROUTER", ModelRouter((provider,))),
        ):
            _plan, metadata = server.private_chat_response({"message": f"My Genshin UID is {uid}", "history": []})
            proposal = metadata["memory_proposals"][0]
            self.assertEqual(proposal["sensitivity"], "private")
            self.assertEqual(proposal["value"], uid)
            self.assertIn(uid, provider.requests[-1].prompt)
            self.assertEqual(knowledge.calls, 0)

            memory.approve(proposal["proposal_id"])
            server.private_chat_response({"message": "What is my Genshin UID?", "history": []})

        self.assertEqual(len(provider.requests), 2)
        self.assertIn(uid, provider.requests[-1].prompt)


if __name__ == "__main__":
    unittest.main()
