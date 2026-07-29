from __future__ import annotations

import json
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from apps.orchestrator.src.siduri_orchestrator.contracts import EventEnvelope, MockProvider
from apps.orchestrator.src.siduri_orchestrator.server import Handler
from packages.contracts.interfaces import AdapterStub, CapabilityError
from packages.contracts.repository import InMemoryRepository
from packages.knowledge.fake import FakeKnowledgeSource


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
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = HTTPConnection("127.0.0.1", server.server_port)
            connection.request("GET", "/health")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read())["status"], "ok")
            connection.request("POST", "/dev/mock-response")
            response = connection.getresponse()
            self.assertEqual(response.status, 202)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
