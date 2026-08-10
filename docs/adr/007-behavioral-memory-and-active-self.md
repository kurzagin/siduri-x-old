# ADR 007: Behavioral Memory and Active Self Projection

## Status

Accepted

## Context

Siduri currently stores learned facts in database memory and retrieves them only when a query appears semantically relevant. This works for knowledge recall but fails for persistent behavior. For example, if the user teaches Siduri her name or how to address the user, she may only recall it if the exact keywords are present in the retrieval query.

This exposes a distinction between recall memory (answering "What do I know?") and behavioral memory (answering "How should I behave continuously?"). Siduri is not only a query-driven assistant; she maintains a learned identity and relationship across conversations.

## Decision

Siduri will distinguish recall-oriented memory from behavior-governing memory. Confirmed behavioral directives are compiled into an audience-scoped Active Self projection and included in every applicable model request.

The runtime prompt will be assembled in the following order:
1. Neutral kernel
2. Active Behavioral Memory
3. Deterministically selected semantic knowledge
4. Retrieved episodic memory
5. Current session state
6. Current user message

The provider boundary must preserve this trust distinction: the neutral kernel
and compiled Active Self are sent in the provider's system role. Retrieved and
current-turn material is sent separately as bounded context.

Behavioral memory will be typed, normalized (not raw user text), versioned, inspectable, and approval-gated.

The compiler will filter by active status, current recipient, audience, and validity period. It will resolve conflicts by authority and recency.

## Consequences

- Siduri's identity and behavioral instructions will persist automatically across sessions and contexts when their scopes match.
- The `PromptAssembler` will cleanly separate `<active_behavioral_memory>` from general retrieved episodic memories.
- Operator UI will explicitly distinguish teaching an Identity Fact, Relationship Fact, or Behavioral Rule from standard episodic memories.
- An explicit boundary remains against unsafe prompt injections because behavioral directives are structured, not freeform raw text.
- Knowledge domain and runtime effect are independent as specified by ADR 008;
  relationship knowledge may project into behavior without being reclassified as
  a behavioral fact.
