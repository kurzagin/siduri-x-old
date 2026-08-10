from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable
from uuid import uuid4

from apps.orchestrator.src.siduri_orchestrator.contracts import ResponsePlan
from packages.model_router.router import (AuthenticationProviderFailure, GenerationRequest,
    RateLimitProviderFailure, ServerProviderFailure, TimeoutProviderFailure, ProviderFailure)


class ZaiProviderError(RuntimeError):
    pass


class ZaiStructuredProvider:
    """Minimal standard-library client for Z.AI's GLM chat-completions API."""

    provider_id = "zai-glm-5.2"
    model_id = "glm-5.2"
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
        self.model_id = model
        self.endpoint = base_url.rstrip("/") + "/chat/completions"
        self._opener = opener
        self.last_usage: dict[str, int | float] = {}

    def generate_response(self, request: GenerationRequest) -> ResponsePlan:
        recipient_rule = f" Set recipient exactly to {request.recipient}." if request.recipient else ""
        response_contract = "Return only one JSON object matching this exact Siduri ResponsePlan shape. Do not include markdown, explanations, or reasoning: {recipient:string,intent:string,semantic_summary:string,spoken_ja:string,subtitle_en:string,subtitle_id:string,emotion:string,speech_priority:integer,interruptible:boolean,evidence_ids:string[],confidence:number between 0 and 1,requires_operator_approval:boolean,memory_proposals:[{content:string,subject:string,predicate:string,value:string,claim_type:'semantic'|'preference'|'episodic'|'relationship',provenance:string,sensitivity:'public'|'stream_safe'|'private'|'secret',allowed_audiences:string[]}],behavioral_proposals:[{knowledge_domain:string,runtime_effect:'identity_context'|'relationship_context'|'behavioral_rule',subject:string,predicate:string,value:string,activation:'always'|'always_when_scope_matches',scope:{recipient_ids:string[],audiences:string[],session_modes:string[]},behavior:{instruction:string,frequency:string,preferred_positions:string[]}}]}. memory_proposals are isolated candidates only: propose at most four durable, atomic claims explicitly stated or strongly grounded in the conversation; otherwise return []. Use stable snake_case predicates. For game-account facts use a subject such as primary_user.genshin_account and a precise predicate such as uid, server, or main_character. knowledge_domain describes what a claim is about; runtime_effect separately describes how it changes Siduri at runtime. When one relationship statement also requests behavior, emit a relationship memory_proposal and a separate behavioral_proposal. These are never canonical memory until confirmed. The Japanese, English, and Indonesian fields must express the same meaning."
        system_content = response_contract + recipient_rule
        if request.system_prompt:
            system_content += "\n\n" + request.system_prompt
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_content},
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
            if error.code in (401, 403):
                raise AuthenticationProviderFailure("Z.AI authentication failed") from error
            if error.code == 429:
                raise RateLimitProviderFailure("Z.AI rate limit") from error
            if 500 <= error.code < 600:
                raise ServerProviderFailure(f"Z.AI server error {error.code}") from error
            raise ProviderFailure(f"Z.AI request failed with HTTP {error.code}") from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise TimeoutProviderFailure("Z.AI request timed out or was unreachable") from error
        except json.JSONDecodeError as error:
            raise ProviderFailure("Z.AI returned invalid transport JSON") from error
        self.last_usage = self._usage(response_body.get("usage")) if isinstance(response_body, dict) else {}
        return self._parse_response(response_body, request.recipient)

    @staticmethod
    def _usage(value: object) -> dict[str, int | float]:
        if not isinstance(value, dict):
            return {}
        result: dict[str, int | float] = {}
        for source, target in (("prompt_tokens", "prompt_tokens"), ("completion_tokens", "completion_tokens"), ("total_tokens", "total_tokens")):
            if isinstance(value.get(source), int) and not isinstance(value[source], bool):
                result[target] = value[source]
        if isinstance(value.get("cost_usd"), (int, float)) and not isinstance(value["cost_usd"], bool):
            result["cost_usd"] = float(value["cost_usd"])
        return result

    def _parse_response(self, value: object, expected_recipient: str | None = None) -> ResponsePlan:
        try:
            content = value["choices"][0]["message"]["content"]  # type: ignore[index]
            parsed = json.loads(content) if isinstance(content, str) else content
            if not isinstance(parsed, dict):
                raise ValueError("model content was not a JSON object")
            return ResponsePlan.from_dict(parsed, expected_recipient)
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ZaiProviderError("Z.AI returned invalid Siduri response JSON") from error
