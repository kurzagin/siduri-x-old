"""Provider and integration boundaries. Implementations must declare capabilities."""
from __future__ import annotations

from dataclasses import dataclass
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
