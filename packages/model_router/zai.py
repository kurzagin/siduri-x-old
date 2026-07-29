from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable
from uuid import uuid4

from apps.orchestrator.src.siduri_orchestrator.contracts import ResponsePlan
from packages.model_router.router import GenerationRequest


class ZaiProviderError(RuntimeError):
    pass


class ZaiStructuredProvider:
    """Minimal standard-library client for Z.AI's GLM chat-completions API."""

    provider_id = "zai-glm-5.2"
    capabilities = frozenset({"text_generation", "structured_generation"})

    def __init__(
        self,
        api_key: str,
        model: str = "glm-5.2",
        base_url: str = "https://api.z.ai/api/paas/v4",
        opener: Callable[..., Any] = urllib.request.urlopen,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Z.AI API key must not be empty")
        self.api_key = api_key
        self.model = model
        self.endpoint = base_url.rstrip("/") + "/chat/completions"
        self._opener = opener

    def generate_response(self, request: GenerationRequest) -> ResponsePlan:
        recipient_rule = f" Set recipient exactly to {request.recipient}." if request.recipient else ""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Return only one JSON object matching this exact Siduri ResponsePlan shape. Do not include markdown, explanations, or reasoning: {recipient:string,intent:string,semantic_summary:string,spoken_ja:string,subtitle_en:string,subtitle_id:string,emotion:string,speech_priority:integer,interruptible:boolean,evidence_ids:string[],confidence:number between 0 and 1,requires_operator_approval:boolean}. The Japanese, English, and Indonesian fields must express the same meaning." + recipient_rule},
                {"role": "user", "content": "Generate the response plan for this bounded context:\n" + request.prompt},
            ],
            "thinking": {"type": "disabled"},
            "temperature": 0.0,
            "max_tokens": 1200,
            "response_format": {"type": "json_object"},
            "request_id": f"siduri-{uuid4().hex}",
        }
        body = json.dumps(payload).encode("utf-8")
        request_object = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept-Language": "en-US,en",
            },
            method="POST",
        )
        try:
            with self._opener(request_object, timeout=request.timeout_seconds) as response:
                response_body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise ZaiProviderError(f"Z.AI request failed with HTTP {error.code}") from error
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            raise ZaiProviderError("Z.AI request failed before a valid response was received") from error
        return self._parse_response(response_body, request.recipient)

    def _parse_response(self, value: object, expected_recipient: str | None = None) -> ResponsePlan:
        try:
            content = value["choices"][0]["message"]["content"]  # type: ignore[index]
            parsed = json.loads(content) if isinstance(content, str) else content
            if not isinstance(parsed, dict):
                raise ValueError("model content was not a JSON object")
            required = ("recipient", "intent", "semantic_summary", "spoken_ja", "subtitle_en", "subtitle_id")
            missing = [key for key in required if not parsed.get(key)]
            if missing:
                raise ValueError(f"missing response fields: {', '.join(missing)}")
            evidence_ids = parsed.get("evidence_ids", [])
            if not isinstance(evidence_ids, list) or not all(isinstance(item, str) for item in evidence_ids):
                raise ValueError("evidence_ids must be a list of strings")
            confidence = float(parsed.get("confidence", 0.0))
            if not 0.0 <= confidence <= 1.0:
                raise ValueError("confidence must be between 0 and 1")
            if expected_recipient is not None and str(parsed["recipient"]) != expected_recipient:
                raise ValueError("model recipient does not match the requested audience")
            return ResponsePlan(
                recipient=str(parsed["recipient"]),
                intent=str(parsed["intent"]),
                semantic_summary=str(parsed["semantic_summary"]),
                spoken_ja=str(parsed["spoken_ja"]),
                subtitle_en=str(parsed["subtitle_en"]),
                subtitle_id=str(parsed["subtitle_id"]),
                emotion=str(parsed.get("emotion", "observant")),
                speech_priority=int(parsed.get("speech_priority", 50)),
                interruptible=bool(parsed.get("interruptible", True)),
                evidence_ids=tuple(evidence_ids),
                confidence=confidence,
                requires_operator_approval=bool(parsed.get("requires_operator_approval", False)),
            )
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ZaiProviderError("Z.AI returned invalid Siduri response JSON") from error
