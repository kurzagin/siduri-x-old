from __future__ import annotations

from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from time import monotonic, sleep
from typing import Protocol

from apps.orchestrator.src.siduri_orchestrator.contracts import ResponsePlan
from .telemetry import TelemetryRecorder
from .validation import ResponsePlanValidationError, validate_response_plan


@dataclass(frozen=True)
class GenerationRequest:
    task: str
    prompt: str
    required_capabilities: frozenset[str] = frozenset({"structured_generation"})
    timeout_seconds: float = 10.0
    recipient: str | None = None
    max_retries: int = 1


class StructuredProvider(Protocol):
    provider_id: str
    model_id: str
    capabilities: frozenset[str]
    def generate_response(self, request: GenerationRequest) -> ResponsePlan: ...


class NoProviderError(RuntimeError):
    pass


class ProviderUnavailableError(RuntimeError):
    pass


class ProviderFailure(RuntimeError):
    retryable = False
    category = "provider_failure"


class TransientProviderFailure(ProviderFailure):
    retryable = True


class TimeoutProviderFailure(TransientProviderFailure):
    category = "timeout"


class AuthenticationProviderFailure(ProviderFailure):
    category = "authentication"


class RateLimitProviderFailure(TransientProviderFailure):
    category = "rate_limit"


class ServerProviderFailure(TransientProviderFailure):
    category = "server_error"


class MockStructuredProvider:
    provider_id = "mock-structured"
    model_id = "mock"
    capabilities = frozenset({"text_generation", "structured_generation"})

    def generate_response(self, request: GenerationRequest) -> ResponsePlan:
        return ResponsePlan(recipient=request.recipient or "master_stream", intent=request.task,
            semantic_summary="Siduri is responding from a bounded identity and memory context.",
            spoken_ja="ご主人、確認できる範囲でお答えします。不確かな情報は、確かなふりをしません。",
            subtitle_en="Master, I will answer within the confirmed context. I will not pretend uncertain information is certain.",
            subtitle_id="Master, aku akan menjawab berdasarkan konteks yang terkonfirmasi. Aku tidak akan berpura-pura yakin pada informasi yang belum pasti.",
            emotion="observant", confidence=0.9)


class AlternateStructuredProvider(MockStructuredProvider):
    """Second company-neutral test double for provider registration and routing tests."""
    provider_id = "alternate-structured"
    model_id = "alternate-test-model"


@dataclass
class _Circuit:
    failures: int = 0
    opened_until: float = 0.0


class ModelRouter:
    def __init__(self, providers: tuple[StructuredProvider, ...], telemetry: TelemetryRecorder | None = None,
                 failure_threshold: int = 3, cooldown_seconds: float = 30.0) -> None:
        self.providers = providers
        self.telemetry = telemetry or TelemetryRecorder()
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._circuits = {provider.provider_id: _Circuit() for provider in providers}

    def generate(self, request: GenerationRequest) -> ResponsePlan:
        attempted = False
        failures: list[str] = []
        self.telemetry.record("request_started", task=request.task, recipient=request.recipient,
                              required_capabilities=sorted(request.required_capabilities))
        for provider in self.providers:
            if not request.required_capabilities.issubset(provider.capabilities):
                continue
            circuit = self._circuits[provider.provider_id]
            if circuit.opened_until > monotonic():
                self.telemetry.record("provider_skipped", provider_id=provider.provider_id, reason="circuit_open")
                continue
            attempted = True
            for attempt in range(request.max_retries + 1):
                started = self.telemetry.timer()
                try:
                    result = validate_response_plan(self._invoke(provider, request), request.recipient)
                    circuit.failures = 0
                    usage = getattr(provider, "last_usage", {})
                    self.telemetry.record("request_completed", provider_id=provider.provider_id, model_id=getattr(provider, "model_id", provider.provider_id), latency_ms=round((monotonic() - started) * 1000, 2), attempt=attempt + 1, **usage)
                    if attempt:
                        self.telemetry.record("retry_succeeded", provider_id=provider.provider_id)
                    return result
                except Exception as error:
                    failure = self._classify(error)
                    failures.append(f"{provider.provider_id}: {failure.category}")
                    self.telemetry.record("provider_failure", provider_id=provider.provider_id, category=failure.category, retryable=failure.retryable)
                    if not failure.retryable or attempt >= request.max_retries:
                        break
                    sleep(0.01)
            circuit.failures += 1
            if circuit.failures >= self.failure_threshold:
                circuit.opened_until = monotonic() + self.cooldown_seconds
                self.telemetry.record("circuit_state_changed", provider_id=provider.provider_id, state="open")
            self.telemetry.record("fallback", provider_id=provider.provider_id)
        if not attempted:
            required = ", ".join(sorted(request.required_capabilities))
            raise NoProviderError(f"no provider supports required capabilities: {required}")
        self.telemetry.record("degraded_mode", failures=failures)
        return ResponsePlan(
            recipient=request.recipient or "master_stream", intent="degraded_mode",
            semantic_summary="No configured model provider completed this request; Siduri is in degraded mode.",
            spoken_ja="現在、モデル応答を確認できません。安全のため、待機状態に戻ります。",
            subtitle_en="No model response could be confirmed. For safety, I am returning to standby.",
            subtitle_id="Tidak ada respons model yang dapat dikonfirmasi. Demi keamanan, aku kembali menunggu.",
            emotion="cautious", confidence=0.0, requires_operator_approval=False)

    @staticmethod
    def _classify(error: Exception) -> ProviderFailure:
        if isinstance(error, ResponsePlanValidationError):
            return ProviderFailure("malformed response")
        if isinstance(error, TimeoutError):
            return TimeoutProviderFailure("timeout")
        return error if isinstance(error, ProviderFailure) else ProviderFailure(str(error))

    @staticmethod
    def _invoke(provider: StructuredProvider, request: GenerationRequest) -> ResponsePlan:
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="siduri-provider")
        future = executor.submit(provider.generate_response, request)
        try:
            return future.result(timeout=request.timeout_seconds)
        except FutureTimeout as error:
            future.cancel()
            raise TimeoutProviderFailure("provider request exceeded timeout") from error
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
