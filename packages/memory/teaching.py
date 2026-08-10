"""Deterministic extraction for explicit, high-value private teaching statements.

The model may propose broader memories, but identity, relationship, address, and
game-account basics should not depend solely on probabilistic classification.
Every result remains a pending candidate until the primary user confirms it.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from packages.persona.domain import Recipient


@dataclass(frozen=True)
class TeachingExtraction:
    claims: tuple[dict[str, Any], ...] = ()
    runtime_effects: tuple[dict[str, Any], ...] = ()


def _claim(
    subject: str,
    predicate: str,
    value: str,
    claim_type: str = "semantic",
    content: str | None = None,
    sensitivity: str = "private",
) -> dict[str, Any]:
    return {
        "content": content or f"{subject} {predicate} = {value}",
        "subject": subject,
        "predicate": predicate,
        "value": value,
        "claim_type": claim_type,
        "provenance": "explicit_private_teaching",
        "sensitivity": sensitivity,
        "allowed_audiences": [Recipient.MASTER_PRIVATE.value],
    }


def _runtime(
    *,
    knowledge_domain: str,
    runtime_effect: str,
    subject: str,
    predicate: str,
    value: str,
    instruction: str = "",
    audiences: tuple[str, ...] = (),
) -> dict[str, Any]:
    effect_to_class = {
        "identity_context": "identity",
        "relationship_context": "relationship",
        "behavioral_rule": "behavioral",
    }
    return {
        "memory_class": effect_to_class[runtime_effect],
        "runtime_effect": runtime_effect,
        "knowledge_domain": knowledge_domain,
        "domain": knowledge_domain,
        "subject": subject,
        "predicate": predicate,
        "value": value,
        "activation": "always_when_scope_matches" if audiences else "always",
        "scope": {"recipient_ids": [], "audiences": list(audiences), "session_modes": []},
        "behavior": {
            "instruction": instruction,
            "frequency": "contextual",
            "preferred_positions": [],
        },
    }


def _clean_value(value: str, limit: int = 160) -> str:
    return re.sub(r"\s+", " ", value).strip(" .,!?:;\"'")[:limit]


def extract_explicit_teaching(message: str) -> TeachingExtraction:
    text = _clean_value(message, 1000)
    claims: list[dict[str, Any]] = []
    effects: list[dict[str, Any]] = []

    match = re.search(
        r"\b(?:your name is|you are called)\s+(.+?)(?=\s+and\s+(?:i\b|my\b|you\b)|[.;,]|$)",
        text,
        re.IGNORECASE,
    )
    if match:
        name = _clean_value(match.group(1), 80)
        claims.append(_claim("siduri", "name", name, content=f"Siduri's name is {name}."))
        effects.append(_runtime(
            knowledge_domain="identity",
            runtime_effect="identity_context",
            subject="siduri",
            predicate="name",
            value=name,
        ))

    match = re.search(
        r"\bmy name is\s+(.+?)(?=\s+and\s+(?:i\b|my\b|you\b)|[.;,]|$)",
        text,
        re.IGNORECASE,
    )
    if match and not re.search(r"\b(?:private|public|stream|everywhere)\b", text, re.IGNORECASE):
        name = _clean_value(match.group(1), 80)
        claims.append(_claim("primary_user", "name", name, content=f"The primary user's name is {name}."))
        effects.append(_runtime(
            knowledge_domain="relationship",
            runtime_effect="relationship_context",
            subject="primary_user",
            predicate="name",
            value=name,
        ))

    if re.search(r"\b(?:i am|i'm)\s+your\s+creator\b", text, re.IGNORECASE):
        claims.append(_claim(
            "primary_user",
            "relationship_to_siduri",
            "creator",
            "relationship",
            "The primary user is Siduri's creator.",
        ))
        effects.append(_runtime(
            knowledge_domain="relationship",
            runtime_effect="relationship_context",
            subject="primary_user",
            predicate="relationship_to_siduri",
            value="creator",
        ))

    match = re.search(
        r"\b(?:(?:from now on|only),?\s*)?call me\s+(.+?)(?:\s+(in private|privately|on stream|in public|publicly|everywhere))?(?=\s+and\s+(?:i\b|my\b|you\b)|[.;,]|$)",
        text,
        re.IGNORECASE,
    )
    if match:
        address = _clean_value(match.group(1), 80)
        scope_phrase = (match.group(2) or "").casefold()
        if "private" in scope_phrase or "privately" in scope_phrase:
            audiences = (Recipient.MASTER_PRIVATE.value,)
            scope_text = "in private conversations"
        elif "stream" in scope_phrase or "public" in scope_phrase:
            audiences = (Recipient.MASTER_STREAM.value, Recipient.VIEWER_DIRECT.value, Recipient.AUDIENCE_GENERAL.value)
            scope_text = "in public and stream conversations"
        else:
            audiences = ()
            scope_text = "when addressing the primary user"
        claims.append(_claim(
            "primary_user",
            "preferred_address",
            address,
            "relationship",
            f"The primary user's preferred address is {address}.",
        ))
        effects.append(_runtime(
            knowledge_domain="relationship",
            runtime_effect="behavioral_rule",
            subject="primary_user",
            predicate="preferred_address",
            value=address,
            instruction=f"Address the primary user as {address} {scope_text}.",
            audiences=audiences,
        ))

    game_patterns = (
        (r"\bmy\s+(?:genshin(?: impact)?\s+)?uid\s+is\s+([0-9]{6,12})", "uid", 16),
        (r"\bmy\s+genshin\s+server\s+is\s+(.+?)(?=\s+and\s+my\b|[.;,]|$)", "server", 40),
        (r"\bmy\s+(?:genshin\s+)?main\s+character\s+is\s+(.+?)(?=\s+and\s+my\b|[.;,]|$)", "main_character", 100),
        (r"\bmy\s+(?:genshin\s+)?account\s+name\s+is\s+(.+?)(?=\s+and\s+my\b|[.;,]|$)", "account_name", 100),
    )
    for pattern, predicate, limit in game_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            claims.append(_claim(
                "primary_user.genshin_account",
                predicate,
                _clean_value(match.group(1), limit),
                content=f"The primary user's Genshin account {predicate.replace('_', ' ')} is {_clean_value(match.group(1), limit)}.",
                sensitivity="private",
            ))

    return TeachingExtraction(tuple(claims), tuple(effects))
