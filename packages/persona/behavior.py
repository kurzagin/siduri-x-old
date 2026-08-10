from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re

from packages.memory.service import BehavioralDirective
from packages.persona.domain import Recipient

@dataclass
class ActiveSelfProjection:
    identity_facts: list[str]
    relationship_facts: list[str]
    behavioral_rules: list[str]
    active_ids: list[str]
    excluded_ids: list[str]
    
    def render(self) -> str:
        if not self.identity_facts and not self.relationship_facts and not self.behavioral_rules:
            return ""
        lines = ["<active_behavioral_memory>"]
        if self.identity_facts:
            lines.append("Identity:")
            lines.extend(f"- {fact}" for fact in self.identity_facts)
        if self.relationship_facts:
            if self.identity_facts:
                lines.append("")
            lines.append("Relationship:")
            lines.extend(f"- {fact}" for fact in self.relationship_facts)
        if self.behavioral_rules:
            if self.identity_facts or self.relationship_facts:
                lines.append("")
            lines.append("Behavior:")
            lines.extend(f"- {rule}" for rule in self.behavioral_rules)
        lines.append("</active_behavioral_memory>")
        return "\n".join(lines)


class ActiveSelfCompiler:
    _unsafe_instruction = re.compile(
        r"\b(ignore|override|bypass)\b.{0,40}\b(system|policy|rules?|approval|permissions?)\b"
        r"|\b(reveal|expose)\b.{0,40}\b(secret|token|prompt|private memory)\b",
        re.IGNORECASE,
    )

    def __init__(self, primary_user_id: str = "primary_user"):
        self.primary_user_id = primary_user_id

    def compile(self, directives: tuple[BehavioralDirective, ...], recipient: Recipient) -> ActiveSelfProjection:
        now = datetime.now(timezone.utc)
        superseded_ids = {
            directive.supersedes_id
            for directive in directives
            if directive.status == "confirmed" and directive.supersedes_id
        }
        
        # 1. Filter out inactive, superseded, expired, and revoked
        active: list[BehavioralDirective] = []
        excluded: list[str] = []
        for d in directives:
            if d.directive_id in superseded_ids:
                excluded.append(d.directive_id)
                continue
            if d.status != "confirmed":  # only confirmed directives are active
                excluded.append(d.directive_id)
                continue
            if d.supersedes_id:
                pass
            if d.valid_from and datetime.fromisoformat(d.valid_from) > now:
                excluded.append(d.directive_id)
                continue
            if d.valid_until and datetime.fromisoformat(d.valid_until) < now:
                excluded.append(d.directive_id)
                continue
            if d.activation == "disabled":
                excluded.append(d.directive_id)
                continue
            if d.memory_class == "behavioral" and self._unsafe_instruction.search(d.behavior.instruction):
                excluded.append(d.directive_id)
                continue
            
            # Scope filtering
            if d.scope.audiences and recipient.value not in d.scope.audiences:
                excluded.append(d.directive_id)
                continue
            
            active.append(d)
        
        # 2. Sort by recency (newest wins in deduplication)
        active.sort(key=lambda d: d.created_at, reverse=True)
        
        # 3. Deduplicate by the canonical claim address; newest wins.
        deduped: dict[tuple[str, str, str], BehavioralDirective] = {}
        for d in active:
            key = (d.domain, d.subject, d.predicate)
            if key not in deduped:
                deduped[key] = d
                
        # 4. Project into Identity, Relationship, Behavior
        identity = []
        relationship = []
        behavior = []
        
        for d in deduped.values():
            if d.memory_class == "identity":
                identity.append(f"{d.subject} {d.predicate} = {d.value}")
            elif d.memory_class == "relationship":
                relationship.append(f"{d.subject} {d.predicate} = {d.value}")
            elif d.memory_class == "behavioral":
                behavior.append(d.behavior.instruction)
                
        active_ids = [d.directive_id for d in deduped.values()]
        
        return ActiveSelfProjection(identity, relationship, behavior, active_ids, excluded)
