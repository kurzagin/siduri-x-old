"""Z.AI GLM-5V adapter behind the provider-neutral vision contract.

HTTP transport is injected so tests stay credential-free and a future ChatGPT
adapter can implement the same contract without changing observation code.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from typing import Protocol

from packages.observation.pipeline import VisionReading

from .contract import VisionProviderError, VisionRequest


class VisionTransport(Protocol):
    def complete(self, *, model: str, instruction: str, image_data_url: str) -> object: ...


class ZaiGlm5VisionProvider:
    provider_id = "zai"

    def __init__(self, transport: VisionTransport, model: str = "glm-5v-turbo") -> None:
        self.transport = transport
        self.model_id = model

    def analyze(self, request: VisionRequest) -> tuple[VisionReading, ...]:
        data_url = f"data:{request.mime_type};base64,{base64.b64encode(request.image).decode('ascii')}"
        raw = self.transport.complete(model=self.model_id, instruction=request.instruction, image_data_url=data_url)
        if isinstance(raw, dict) and isinstance(raw.get("readings"), list):
            items = raw["readings"]
        elif isinstance(raw, dict):
            items = [raw]
        elif isinstance(raw, list):
            items = raw
        else:
            raise VisionProviderError("vision provider returned an invalid normalized response")
        readings: list[VisionReading] = []
        for item in items[:32]:
            if not isinstance(item, dict):
                continue
            try:
                entity = item.get("entity", item.get("type"))
                value = item.get("value", item.get("observation"))
                alternatives = item.get("competing_interpretations", [])
                if not isinstance(alternatives, list):
                    alternatives = []
                if not isinstance(entity, str) or not isinstance(value, str):
                    # Some vision models return a keyed state object despite the
                    # requested normalized schema. Preserve those scalar fields
                    # as separate low-confidence readings instead of discarding
                    # visible evidence.
                    for key, raw_value in item.items():
                        if isinstance(raw_value, (str, int, float, bool)):
                            readings.append(VisionReading(str(key), str(raw_value), 0.5, ocr_text=None))
                    continue
                readings.append(VisionReading(
                    entity=entity, value=value,
                    confidence=float(item.get("confidence", 0.5)), source_crop=str(item.get("source_crop", "full-frame")),
                    ocr_text=str(item.get("ocr_text", item.get("evidence", item.get("details")))) if item.get("ocr_text", item.get("evidence", item.get("details"))) is not None else None,
                    competing_interpretations=tuple(str(value) for value in alternatives[:8]),
                ))
            except (KeyError, TypeError, ValueError):
                continue
        return tuple(readings)


class ZaiGlm5VisionTransport:
    """Standard-library chat-completions transport for GLM-5V-compatible APIs."""

    def __init__(self, api_key: str, base_url: str = "https://api.z.ai/api/paas/v4", *, timeout_seconds: float = 30.0) -> None:
        if not api_key.strip():
            raise ValueError("Z.AI API key must not be empty")
        self.api_key = api_key
        self.endpoint = base_url.rstrip("/") + "/chat/completions"
        self.timeout_seconds = timeout_seconds

    def complete(self, *, model: str, instruction: str, image_data_url: str) -> object:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": instruction},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ]}],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(self.endpoint, data=json.dumps(payload).encode(), headers={
            "Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json", "Accept": "application/json",
        }, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise VisionProviderError(f"Z.AI vision request failed with HTTP {error.code}") from error
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            raise VisionProviderError("Z.AI vision request failed") from error
        try:
            content = body["choices"][0]["message"]["content"]
            parsed = json.loads(content) if isinstance(content, str) else content
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise VisionProviderError("Z.AI vision response was malformed") from error
        return parsed
