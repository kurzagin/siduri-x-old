import unittest
from unittest.mock import patch
from dataclasses import dataclass

from apps.orchestrator.src.siduri_orchestrator import server
from packages.model_router.router import MockStructuredProvider, ModelRouter
from apps.orchestrator.src.siduri_orchestrator.contracts import ResponsePlan


class ChatTests(unittest.TestCase):
    def test_private_chat_uses_private_recipient_without_public_broadcast(self) -> None:
        router = ModelRouter((MockStructuredProvider(),))
        with patch.object(server, "ROUTER", router):
            plan, metadata = server.private_chat_response({"message": "Hello, Siduri", "history": []})
        self.assertEqual(plan.recipient, "master_private")
        self.assertFalse(plan.requires_operator_approval)
        self.assertEqual(metadata["channel"], "private_chat")

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


if __name__ == "__main__":
    unittest.main()
