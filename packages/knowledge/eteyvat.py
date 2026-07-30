from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


class EteyvatError(RuntimeError):
    pass


@dataclass(frozen=True)
class EteyvatResult:
    result_id: str
    title: str
    content: str
    url: str
    source: str = "eteyvat"
    revision: str | None = None
    preview: bool = False
    trusted_domain: bool = True


class EteyvatKnowledgeSource:
    """Read-only adapter for the authoritative E-Teyvat Genshin knowledge base."""

    source_id = "eteyvat"
    capabilities = frozenset({"knowledge_search", "entity_lookup", "farming_sources"})
    trusted_domain = True

    def __init__(self, base_url: str = "https://eteyvat.krzgn.xyz", timeout_seconds: float = 5.0,
                 opener: Callable[..., Any] = urllib.request.urlopen) -> None:
        parsed = urllib.parse.urlparse(base_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("E-Teyvat endpoint must be an absolute HTTPS URL")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._opener = opener
        self._revision: str | None = None

    @property
    def revision(self) -> str | None:
        return self._revision

    def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        query = urllib.parse.urlencode(params)
        request = urllib.request.Request(self.base_url + path + ("?" + query if query else ""), headers={"Accept": "application/json"})
        try:
            with self._opener(request, timeout=self.timeout_seconds) as response:
                value = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise EteyvatError("E-Teyvat request failed") from error
        if not isinstance(value, dict):
            raise EteyvatError("E-Teyvat response was not an object")
        return value

    def health(self) -> bool:
        try:
            value = self._get("/api/health", {})
            self._revision = str(value.get("revision")) if value.get("revision") else self._revision
            return value.get("status") == "ready" and value.get("connected") is True
        except EteyvatError:
            return False

    def search(self, query: str, limit: int = 8) -> list[EteyvatResult]:
        if not query.strip():
            return []
        bounded = max(1, min(50, limit))
        value = self._get("/api/knowledge/search", {"q": query[:200], "limit": str(bounded)})
        self._revision = str(value.get("revision")) if value.get("revision") else self._revision
        preview = value.get("preview") is True
        results: list[EteyvatResult] = []
        for item in value.get("items", []):
            if not isinstance(item, dict) or not isinstance(item.get("content"), str):
                continue
            slug = str(item.get("slug", "unknown"))
            results.append(EteyvatResult(f"eteyvat:{item.get('entity_id', slug)}", str(item.get("name", slug)), item["content"], f"{self.base_url}/api/entities/{item.get('kind', 'entities')}/{slug}", revision=self._revision, preview=preview))
        return results

    def find_entity(self, query: str, kind: str | None = None, limit: int = 5) -> list[EteyvatResult]:
        if not query.strip():
            return []
        params = {"q": query[:200], "limit": str(max(1, min(50, limit)))}
        if kind:
            params["kind"] = kind[:80]
        value = self._get("/api/entities", params)
        preview = value.get("preview") is True
        return [EteyvatResult(f"eteyvat:entity:{item.get('id', item.get('slug', 'unknown'))}", str(item.get("name", item.get("slug", "unknown"))), json.dumps(item, ensure_ascii=False, separators=(",", ":")), f"{self.base_url}/api/entities/{item.get('kind', 'entities')}/{item.get('slug', '')}", revision=self._revision, preview=preview) for item in value.get("items", []) if isinstance(item, dict)]

    def farming_sources(self, target: str) -> dict[str, Any]:
        if not target.strip():
            return {"source": self.source_id, "revision": self._revision, "preview": False, "data": {}}
        value = self._get("/api/farming", {"target": target[:200]})
        self._revision = str(value.get("revision")) if value.get("revision") else self._revision
        return {"source": self.source_id, "revision": self._revision, "preview": value.get("preview") is True, "data": value}
