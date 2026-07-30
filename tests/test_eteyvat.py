from __future__ import annotations

import json
import unittest

from packages.knowledge.eteyvat import EteyvatKnowledgeSource


class FakeResponse:
    def __init__(self, value: object) -> None:
        self.value = value
    def __enter__(self) -> "FakeResponse": return self
    def __exit__(self, *_: object) -> None: return None
    def read(self) -> bytes: return json.dumps(self.value).encode()


class EteyvatTests(unittest.TestCase):
    def test_trusted_source_preserves_revision_and_citations(self) -> None:
        def opener(request: object, timeout: float) -> FakeResponse:
            url = str(getattr(request, "full_url"))
            if "/api/health" in url:
                return FakeResponse({"status": "ready", "connected": True, "revision": "rev-1"})
            return FakeResponse({"items": [{"entity_id": 7, "kind": "characters", "slug": "furina", "name": "Furina", "content": "Hydro."}], "preview": False})

        source = EteyvatKnowledgeSource(opener=opener)
        self.assertTrue(source.health())
        result = source.search("Furina")[0]
        self.assertTrue(result.trusted_domain)
        self.assertEqual(result.url, "https://eteyvat.krzgn.xyz/api/entities/characters/furina")
        self.assertEqual(source.revision, "rev-1")

    def test_endpoint_must_be_https(self) -> None:
        with self.assertRaises(ValueError):
            EteyvatKnowledgeSource("http://localhost:3000")


if __name__ == "__main__":
    unittest.main()
