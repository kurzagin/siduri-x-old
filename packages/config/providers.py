from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


SUPPORTED_TASKS = frozenset({"text_generation", "structured_generation", "vision", "web_search", "tool_calling"})


@dataclass(frozen=True)
class ProviderConfig:
    provider_id: str
    model_id: str
    endpoint: str | None
    capabilities: frozenset[str]
    timeout_seconds: float = 10.0
    token_budget: int = 1200
    enabled: bool = True
    api_key_env: str | None = None

    def validate(self) -> None:
        if not self.provider_id or not self.model_id:
            raise ValueError("provider_id and model_id are required")
        if self.timeout_seconds <= 0 or self.timeout_seconds > 120:
            raise ValueError("timeout_seconds must be between 0 and 120")
        if self.token_budget <= 0 or self.token_budget > 100_000:
            raise ValueError("token_budget is outside the safe bound")
        unknown = self.capabilities - SUPPORTED_TASKS
        if unknown:
            raise ValueError(f"unsupported provider capabilities: {', '.join(sorted(unknown))}")
        if self.endpoint:
            parsed = urlparse(self.endpoint)
            if parsed.scheme not in {"https", "http"} or not parsed.netloc:
                raise ValueError("provider endpoint must be an absolute HTTP(S) URL")
            if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost"}:
                raise ValueError("non-local provider endpoints must use HTTPS")


def configured_provider_state(config: ProviderConfig, credential_present: bool) -> dict[str, object]:
    config.validate()
    return {"provider_id": config.provider_id, "model_id": config.model_id,
            "enabled": config.enabled, "configured": bool(credential_present or not config.api_key_env),
            "capabilities": sorted(config.capabilities), "timeout_seconds": config.timeout_seconds,
            "token_budget": config.token_budget}
