"""Provider and integration boundaries. Implementations must declare capabilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from typing import Protocol


CAPABILITIES = (
    "text_generation", "structured_generation", "vision", "embeddings", "web_search",
    "speech_recognition", "text_to_speech", "tool_calling",
)


@dataclass(frozen=True)
class CapabilityDeclaration:
    provider_id: str
    capabilities: frozenset[str]


class CapabilityError(RuntimeError):
    pass


class Provider(Protocol):
    declaration: CapabilityDeclaration


class KnowledgeSource(Protocol):
    source_id: str
    capabilities: frozenset[str]

    def health(self) -> bool: ...
    def search(self, query: str) -> list[dict[str, str]]: ...


class AdapterStub:
    def __init__(self, provider_id: str, capabilities: frozenset[str] = frozenset()) -> None:
        self.declaration = CapabilityDeclaration(provider_id, capabilities)

    def require(self, capability: str) -> None:
        if capability not in self.declaration.capabilities:
            raise CapabilityError(f"{self.declaration.provider_id} does not support {capability!r}")


class VisionAdapter(AdapterStub):
    def observe(self, frame: bytes) -> None:
        self.require("vision")


class VoicevoxAdapter(AdapterStub):
    def synthesize(self, text: str) -> bytes:
        self.require("text_to_speech")
        raise NotImplementedError("VOICEVOX integration is reserved for a later slice")


class ObsAdapter(AdapterStub):
    def screenshot(self, source_name: str) -> bytes:
        self.require("obs_screenshot")
        raise NotImplementedError("OBS WebSocket v5 integration is reserved for a later slice")


class PlatformAdapter(AdapterStub):
    def send(self, message: str) -> None:
        self.require("chat_send")
        raise NotImplementedError("outbound platform actions require a future approved adapter")


class StorageAdapter(AdapterStub):
    def put(self, key: str, content: bytes) -> None:
        self.require("object_storage")
        raise NotImplementedError("storage implementation is reserved for a later slice")


@dataclass(frozen=True)
class VisionObservation:
    observation_id: str
    summary: str
    confidence: float
    source: str


class VisionProvider(Protocol):
    provider_id: str
    capabilities: frozenset[str]
    def observe(self, frame: bytes) -> list[VisionObservation]: ...


@dataclass(frozen=True)
class SearchResult:
    result_id: str
    title: str
    snippet: str
    url: str
    source: str


class WebSearchProvider(Protocol):
    provider_id: str
    capabilities: frozenset[str]
    def search(self, query: str) -> list[SearchResult]: ...


class FakeVisionProvider:
    provider_id = "fake-vision"
    capabilities = frozenset({"vision"})
    def observe(self, frame: bytes) -> list[VisionObservation]:
        return [VisionObservation("vision_fake_1", "No external vision observation configured.", 0.0, self.provider_id)]


class FakeWebSearchProvider:
    provider_id = "fake-web-search"
    capabilities = frozenset({"web_search"})
    def search(self, query: str) -> list[SearchResult]:
        return [SearchResult("search_fake_1", "No external search configured", query, "about:blank", self.provider_id)]


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


def validate_tool_call(value: object, allowed_tools: frozenset[str]) -> ToolCall:
    if not isinstance(value, dict) or not isinstance(value.get("name"), str) or value["name"] not in allowed_tools:
        raise CapabilityError("tool call is not allowed")
    arguments = value.get("arguments", {})
    if not isinstance(arguments, dict):
        raise CapabilityError("tool call arguments must be an object")
    return ToolCall(value["name"], arguments)
