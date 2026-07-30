# ADR 005: Public actions require approval

## Context

Generated replies and moderation-like actions can affect public audiences and must not be autonomous.

## Decision

Every outbound platform action is proposed, durably audited, operator-reviewed, and explicitly sent only after approval. Rejected or sent actions cannot be reviewed again.

## Consequences

Automation remains bounded and auditable. Live operation requires an operator workflow and approved credentials.
