from __future__ import annotations


class FakeKnowledgeSource:
    source_id = "fake-knowledge"
    capabilities = frozenset({"search", "entity_lookup"})

    def health(self) -> bool:
        return True

    def search(self, query: str) -> list[dict[str, str]]:
        return [{"source": self.source_id, "title": "Foundation placeholder", "snippet": f"No live result for: {query}"}]
