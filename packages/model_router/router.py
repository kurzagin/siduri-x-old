from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from apps.orchestrator.src.siduri_orchestrator.contracts import ResponsePlan


@dataclass(frozen=True)
class GenerationRequest:
    task: str
    prompt: str
    required_capabilities: frozenset[str] = frozenset({"structured_generation"})
    timeout_seconds: float = 10.0
    recipient: str | None = None


class StructuredProvider(Protocol):
    provider_id: str
    capabilities: frozenset[str]

    def generate_response(self, request: GenerationRequest) -> ResponsePlan: ...


class NoProviderError(RuntimeError):
    pass


class ProviderUnavailableError(RuntimeError):
    pass


class MockStructuredProvider:
    provider_id = "mock-structured"
    capabilities = frozenset({"text_generation", "structured_generation"})

    def generate_response(self, request: GenerationRequest) -> ResponsePlan:
        return ResponsePlan(
            recipient=request.recipient or "master_stream",
            intent=request.task,
            semantic_summary="Siduri is responding from a bounded identity and memory context.",
            spoken_ja="ご主人、確認できる範囲でお答えします。不確かな情報は、確かなふりをしません。",
            subtitle_en="Master, I will answer within the confirmed context. I will not pretend uncertain information is certain.",
            subtitle_id="Master, aku akan menjawab berdasarkan konteks yang terkonfirmasi. Aku tidak akan berpura-pura yakin pada informasi yang belum pasti.",
            emotion="observant",
            confidence=0.9,
        )


class ModelRouter:
    def __init__(self, providers: tuple[StructuredProvider, ...]) -> None:
        self.providers = providers

    def generate(self, request: GenerationRequest) -> ResponsePlan:
        attempted = False
        failures: list[str] = []
        for provider in self.providers:
            if request.required_capabilities.issubset(provider.capabilities):
                attempted = True
                try:
                    return provider.generate_response(request)
                except Exception as error:  # provider boundary: degrade to the next capable provider
                    failures.append(f"{provider.provider_id}: {type(error).__name__}")
        if attempted:
            raise ProviderUnavailableError("all capable providers failed: " + ", ".join(failures))
        required = ", ".join(sorted(request.required_capabilities))
        raise NoProviderError(f"no provider supports required capabilities: {required}")
