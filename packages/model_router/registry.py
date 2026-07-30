from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .router import StructuredProvider


@dataclass
class ProviderRegistry:
    """Capability-neutral provider registry used to assemble an ordered router."""
    providers: dict[str, StructuredProvider]

    def __init__(self, providers: Iterable[StructuredProvider] = ()) -> None:
        self.providers = {}
        for provider in providers:
            self.register(provider)

    def register(self, provider: StructuredProvider) -> None:
        if not provider.provider_id.strip():
            raise ValueError("provider_id must not be empty")
        if provider.provider_id in self.providers:
            raise ValueError(f"provider already registered: {provider.provider_id}")
        self.providers[provider.provider_id] = provider

    def ordered(self, provider_ids: tuple[str, ...] | None = None) -> tuple[StructuredProvider, ...]:
        if provider_ids is None:
            return tuple(self.providers.values())
        missing = [provider_id for provider_id in provider_ids if provider_id not in self.providers]
        if missing:
            raise ValueError(f"unknown providers: {', '.join(missing)}")
        return tuple(self.providers[provider_id] for provider_id in provider_ids)
