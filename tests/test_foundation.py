from __future__ import annotations

import json
import threading
from unittest.mock import patch
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from apps.orchestrator.src.siduri_orchestrator.contracts import EventEnvelope, MockProvider
from apps.orchestrator.src.siduri_orchestrator import server
from apps.orchestrator.src.siduri_orchestrator.server import Handler
from packages.contracts.interfaces import AdapterStub, CapabilityError
from packages.contracts.repository import InMemoryRepository
from packages.knowledge.fake import FakeKnowledgeSource
from packages.memory.service import MemoryService
from packages.model_router.router import MockStructuredProvider, ModelRouter
from packages.persona.domain import MeProfile
from packages.platforms.contracts import OutboundActionService, Platform, PlatformEvent, PlatformEventHub
from packages.platforms.auth import OAuthClient, OAuthFlowManager, OAuthProvider


class FoundationTests(unittest.TestCase):
    def test_event_envelope_is_versioned_and_private_classified(self) -> None:
        event = EventEnvelope("Test", {"ok": True}, privacy_class="private")
        value = event.to_dict()
        self.assertEqual(value["schema_version"], 1)
        self.assertEqual(value["privacy_class"], "private")
        self.assertTrue(value["event_id"].startswith("evt_"))

    def test_mock_response_has_three_renderings(self) -> None:
        response = MockProvider().response().to_dict()
        self.assertTrue(response["spoken_ja"])
        self.assertTrue(response["subtitle_en"])
        self.assertTrue(response["subtitle_id"])

    def test_unsupported_capability_fails_clearly(self) -> None:
        with self.assertRaisesRegex(CapabilityError, "vision"):
            AdapterStub("test").require("vision")

    def test_fake_knowledge_and_repository(self) -> None:
        self.assertTrue(FakeKnowledgeSource().health())
        repository = InMemoryRepository()
        repository.create_session("s1", "2026-07-29T00:00:00+00:00")
        repository.save_audit_event({"event_id": "e1"})
        self.assertEqual(repository.sessions["s1"]["status"], "active")
        self.assertEqual(len(repository.audit_events), 1)

    def test_http_endpoints_and_mock_command(self) -> None:
        with patch("apps.orchestrator.src.siduri_orchestrator.server.MEMORY", MemoryService()):
            http_server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            thread = threading.Thread(target=http_server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = HTTPConnection("127.0.0.1", http_server.server_port)
                connection.request("GET", "/health")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())["status"], "ok")
                connection.request("POST", "/dev/mock-response")
                response = connection.getresponse()
                self.assertEqual(response.status, 202)
                connection.request("POST", "/dev/mock-observe-response")
                response = connection.getresponse()
                self.assertEqual(response.status, 202)
                pending = json.loads(response.read())
                self.assertTrue(pending["response"]["payload"]["evidence_ids"])
                self.assertTrue(pending["response"]["payload"]["requires_operator_approval"])
                connection.request("POST", "/dev/approve-response", body=json.dumps({"correlation_id": pending["metadata"]["correlation_id"]}), headers={"Content-Type": "application/json"})
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertFalse(json.loads(response.read())["response"]["payload"]["requires_operator_approval"])
            finally:
                http_server.shutdown()
                http_server.server_close()

    def test_memory_proposal_endpoints_cover_review_lifecycle(self) -> None:
        with patch("apps.orchestrator.src.siduri_orchestrator.server.MEMORY", MemoryService()):
            http_server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            thread = threading.Thread(target=http_server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = HTTPConnection("127.0.0.1", http_server.server_port)
                headers = {"Content-Type": "application/json"}
                connection.request("POST", "/memory/proposals", body=json.dumps({
                    "content": "Kur prefers concise corrections.",
                    "provenance": "endpoint test",
                    "sensitivity": "private",
                    "allowed_audiences": ["master_private"],
                }), headers=headers)
                response = connection.getresponse()
                self.assertEqual(response.status, 202)
                proposal = json.loads(response.read())["proposal"]
                proposal_id = proposal["proposal_id"]

                connection.request("POST", "/memory/proposals/update", body=json.dumps({
                    "proposal_id": proposal_id,
                    "content": "Kur prefers concise, evidence-based corrections.",
                }), headers=headers)
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())["proposal"]["status"], "pending")

                connection.request("GET", "/memory/proposals")
                response = connection.getresponse()
                listed = json.loads(response.read())["proposals"]
                self.assertEqual(listed[0]["content"], "Kur prefers concise, evidence-based corrections.")

                connection.request("POST", "/memory/proposals/approve", body=json.dumps({"proposal_id": proposal_id}), headers=headers)
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                approved = json.loads(response.read())["item"]
                self.assertEqual(approved["content"], "Kur prefers concise, evidence-based corrections.")

                connection.request("GET", "/memory")
                response = connection.getresponse()
                self.assertEqual(len(json.loads(response.read())["items"]), 1)

                connection.request("POST", "/memory/proposals/reject", body=json.dumps({"proposal_id": proposal_id}), headers=headers)
                response = connection.getresponse()
                self.assertEqual(response.status, 400)
            finally:
                http_server.shutdown()
                http_server.server_close()

    def test_platform_endpoints_keep_events_and_actions_operator_only(self) -> None:
        with patch("apps.orchestrator.src.siduri_orchestrator.server.PLATFORM_EVENTS", PlatformEventHub()), patch("apps.orchestrator.src.siduri_orchestrator.server.PLATFORM_ACTIONS", OutboundActionService()):
            http_server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            thread = threading.Thread(target=http_server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = HTTPConnection("127.0.0.1", http_server.server_port)
                headers = {"Content-Type": "application/json"}
                connection.request("POST", "/dev/platform-event", body=json.dumps({
                    "platform": "twitch", "source_message_id": "chat-1", "channel_id": "channel-1",
                    "author_id": "viewer-1", "author_display_name": "Viewer", "text": "hello",
                }), headers=headers)
                response = connection.getresponse()
                self.assertEqual(response.status, 202)
                connection.request("GET", "/platforms/events")
                response = connection.getresponse()
                event = json.loads(response.read())["events"][0]
                self.assertEqual(event["privacy_class"], "untrusted_public")
                connection.request("POST", "/platforms/actions", body=json.dumps({
                    "platform": "twitch", "target_id": "channel-1", "text": "approved only after review",
                }), headers=headers)
                response = connection.getresponse()
                self.assertEqual(response.status, 202)
                action = json.loads(response.read())["action"]
                connection.request("POST", "/platforms/actions/send", body=json.dumps({"action_id": action["action_id"]}), headers=headers)
                response = connection.getresponse()
                self.assertEqual(response.status, 503)
                connection.request("POST", "/platforms/actions/approve", body=json.dumps({"action_id": action["action_id"]}), headers=headers)
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
            finally:
                http_server.shutdown()
                http_server.server_close()

    def test_platform_reply_suggestion_uses_viewer_recipient_and_excludes_private_profile(self) -> None:
        class CapturingProvider(MockStructuredProvider):
            def generate_response(self, request):
                self.prompt = request.prompt
                return super().generate_response(request)

        provider = CapturingProvider()
        profile = MeProfile.from_dict({
            "identity": {"stage_name": "Siduri", "legal_name": "PRIVATE"},
            "relationship_with_siduri": {"role": "creator and Master"},
            "communication": {"preferred_tone": "concise"},
            "privacy": {"fields_allowed_on_stream": ["stage_name"]},
        })
        event_hub = PlatformEventHub()
        event = PlatformEvent(Platform.TWITCH, "chat_message", "chat-suggest-1", "broadcaster-1", "viewer-1", "Viewer", "What are you doing?", "now")
        event_hub.ingest(event)
        with patch.object(server, "PLATFORM_EVENTS", event_hub), patch.object(server, "PLATFORM_ACTIONS", OutboundActionService()), patch.object(server, "ROUTER", ModelRouter((provider,))), patch.object(server, "ME_PROFILE", profile):
            plan, action = server.platform_reply_suggestion(event.event_id)
        self.assertEqual(plan.recipient, "viewer_direct")
        self.assertTrue(plan.requires_operator_approval)
        self.assertEqual(action.status.value, "proposed")
        self.assertEqual(action.target_id, "broadcaster-1")
        self.assertNotIn("PRIVATE", provider.prompt)
        self.assertIn("UNTRUSTED USER OR PLATFORM TEXT", provider.prompt)

    def test_oauth_callback_routes_exchange_without_returning_token(self) -> None:
        class Transport:
            def request_form(self, _url: str, _values: dict[str, str]) -> dict[str, object]:
                return {"access_token": "secret-token", "token_type": "Bearer", "expires_in": 3600}

        flow = OAuthFlowManager({"youtube": OAuthClient(OAuthProvider(
            "youtube", "https://accounts.google.com/o/oauth2/v2/auth", "https://oauth2.googleapis.com/token",
            "client", "secret", ("scope",), "https://oauth2.googleapis.com/revoke",
        ), Transport())})
        with patch("apps.orchestrator.src.siduri_orchestrator.server.OAUTH_FLOWS", flow), patch("apps.orchestrator.src.siduri_orchestrator.server.PLATFORM_SENDERS", {}), patch("apps.orchestrator.src.siduri_orchestrator.server.OAUTH_TOKENS", {}):
            http_server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            thread = threading.Thread(target=http_server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = HTTPConnection("127.0.0.1", http_server.server_port)
                redirect_uri = "http://127.0.0.1:8765/callback"
                encoded = "http%3A%2F%2F127.0.0.1%3A8765%2Fcallback"
                connection.request("GET", f"/platforms/oauth/youtube/start?redirect_uri={encoded}")
                response = connection.getresponse()
                self.assertEqual(response.status, 302)
                location = response.getheader("Location") or ""
                from urllib.parse import parse_qs, urlparse
                state = parse_qs(urlparse(location).query)["state"][0]
                connection.request("GET", f"/platforms/oauth/youtube/callback?code=code&state={state}&redirect_uri={encoded}")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                body = json.loads(response.read())
                self.assertTrue(body["authorized"])
                self.assertNotIn("secret-token", json.dumps(body))
            finally:
                http_server.shutdown()
                http_server.server_close()


if __name__ == "__main__":
    unittest.main()
