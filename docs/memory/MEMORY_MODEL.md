# Memory model

For the shipped behavior, UI flow, privacy handling, implementation locations,
and verification evidence, see
[`IMPLEMENTED_MEMORY_AND_BEHAVIOR.md`](IMPLEMENTED_MEMORY_AND_BEHAVIOR.md).

Memory classes are core identity, Me knowledge, preferences, relationship,
episodic, session, and derived summaries. Items retain provenance, confidence,
audiences, timestamps, expiry, supersession, correction, deletion, and approval
state. Single-user Supabase Postgres is authoritative through
`SupabaseMemoryService`; `MemoryService` is the nonpersistent domain/test
implementation. The canonical schema and RLS policies are in
`migrations/002_memory.sql`.

Memory writes use a two-stage authority boundary:

1. Siduri may infer a bounded `memory_proposals` list while answering private chat. Each candidate is stored separately as `pending` and is excluded from canonical retrieval.
2. The operator reviews the candidate in the local console and may edit, approve, or reject it. Approval creates a canonical `MemoryItem`; rejection or an unreviewed candidate never changes canonical memory.

The proposal retains provenance, sensitivity, and audience restrictions. Every proposal mutation is audit logged. Model output cannot directly create canonical memory.

The next memory direction is conversational teaching rather than manual profile
authoring. See [`TEACH_SIDURI.md`](TEACH_SIDURI.md) for the versioned claim
lifecycle, source-event model, temporal conflict handling, natural confirmation
flow, game-data boundaries, and evaluation gates. A generated Me profile is a
projection of confirmed claims; it is not the authority for personal memory.

### Behavioral Memory

Siduri maintains a persistent, context-independent Behavioral Memory layer (ADR-007). Unlike Semantic Memory (which requires relevant keywords to activate), Behavioral Memory instructions are continuously applied to the model context. This includes Identity facts, Relationship facts, and Behavioral instructions.
Behavioral directives are extracted as `behavioral_proposals` during Private Chat, held in `pending` state, and await Operator approval. Confirmed directives are compiled into an `ActiveSelfProjection` and inserted at the highest precedence inside the Prompt Assembler. Active directives can be bounded by audience scope, session modes, and validity periods.

### Claims and runtime effects

Knowledge classification and runtime behavior are separate dimensions (ADR
008). A confirmed relationship claim remains queryable as relationship
knowledge, while an independently approved runtime effect may project that claim
into Active Self. Facts without a runtime effect remain retrieval-only.

The current private teaching path creates atomic `subject / predicate / value`
claim candidates. Approval writes a versioned claim linked to its source event.
Confirmed identity, relationship-context, and behavioral effects are compiled by
recipient and sent to the model provider in the system role. Retrieved personal
and game-account claims remain bounded factual context.

Current development memory contains only information the user deliberately
approves for Siduri to know. Genshin account fields therefore follow the normal
private, single-user Supabase path. Credentials and machine secrets remain
environment configuration. Future local-only memory requires a separate
storage class and policy rather than special cases in this backend.

High-value explicit statements have a deterministic pending-candidate fallback
for Siduri's identity, creator relationship, preferred address, and Genshin
account basics. Broader extraction remains model-assisted and approval-gated.

Retrieval first applies current-status, temporal, sensitivity, and audience
filters. It then combines exact subject/predicate weighting with a generated
Postgres full-text index. Deterministic lexical fallback remains available
without embeddings. Embedding retrieval remains optional future work and must earn its
complexity through evaluation failures rather than replacing exact lookup.
