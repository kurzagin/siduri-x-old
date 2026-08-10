# Implemented memory and learned behavior

## Status

Implemented and verified as of August 8, 2026. The automated suite uses
fictional data. A live GLM teaching, approval, and fresh-conversation behavior
check also passed with an isolated temporary database and fictional values.

Real personal onboarding remains an explicit user-operated action. Siduri does
not infer or import personal account values from repository assets.

## What this implementation achieves

Siduri now has two related but independent ways to use teaching:

1. **Knowledge claims** store what Siduri knows as queryable
   `subject / predicate / value` records.
2. **Runtime effects** control how Siduri behaves, identifies herself, or frames
   her relationship with the primary user.

This separation prevents an ordinary fact from accidentally becoming a system
instruction. It also keeps behavior active on unrelated turns where keyword
retrieval would not find the original teaching.

```text
private teaching
      |
      +--> pending knowledge claim ----approval----> queryable memory
      |
      +--> pending runtime effect -----approval----> Active Self
                                                     |
                                                     +--> provider system role
```

One statement may produce both outputs. For example, “Call me Master in
private” creates a relationship claim and a private behavioral rule. They are
reviewed independently.

## First conversation flow

Open `http://127.0.0.1:3000/chat`. An empty conversation presents four guided,
editable templates:

- behavior: preferred private form of address;
- relationship: user name and creator relationship;
- game profile: Genshin server and main character;
- game profile: Genshin UID.

Bracketed placeholders must be replaced before submission. After sending a
teaching statement, the response displays inline receipts:

- **Remember** is a pending knowledge claim;
- **Runtime effect** is a pending identity, relationship, or behavioral
  projection.

Neither becomes trusted state until the user selects **Approve**. **Reject**
leaves canonical memory and Active Self unchanged. The same review queues are
available in the operator console at `http://127.0.0.1:3000/operator`.

A normal onboarding sequence is:

```text
My name is <name> and I am your creator.
Call me <preferred address> in private.
My Genshin server is <server> and my main character is <character>.
My Genshin UID is <UID>.
```

Each message should be reviewed before continuing. A fresh conversation can
then verify behavior and recall.

## Deterministic teaching

High-value explicit statements do not depend solely on model categorization.
The local extractor creates bounded pending candidates for:

- Siduri's name;
- the primary user's name;
- the creator relationship;
- scoped preferred address;
- Genshin UID, server, account name, and main character.

These candidates still require approval. When GLM describes the same runtime
effect with alternate labels, bounded aliases such as `master_private` and
`preferred_address_private` are canonicalized so the model cannot create a
duplicate or override the deterministic classification.

## Active Self and prompt placement

Confirmed runtime effects are compiled by recipient, audience, validity,
activation state, and supersession. Unsafe directives that attempt to override
policy, permissions, approval, privacy, or system instructions are excluded.

The compiled Active Self is sent through the model provider's **system role**.
Retrieved claims, observations, E-Teyvat data, platform text, chat history, and
the current request remain bounded user-level context. Immutable runtime rules
follow Active Self and retain higher priority.

This makes confirmed behavior persistent across fresh conversations and model
providers without turning retrieved facts into instructions.

E-Teyvat is an optional external knowledge source, not part of Siduri's learned
self or personal memory. Private chat queries it only for an explicit external
knowledge request, such as “Tell me about Hu Tao.” Greetings, ordinary
conversation, self-identity questions, and teaching turns do not query it or
attach E-Teyvat citations.

Internal recipient identifiers such as `master_private` are routing metadata,
not evidence of a creator relationship or preferred title. With no confirmed
relationship or address in Active Self, Siduri must greet the private user
neutrally and must not claim prior personal knowledge.

## Claims, retrieval, and corrections

Approving a knowledge proposal creates:

- a provenance-linked versioned claim;
- a legacy `MemoryItem` compatibility projection.

Canonical retrieval filters status, validity, supersession, sensitivity,
audience, and recipient before ranking. It combines:

- exact subject and predicate matching;
- weighted lexical matching;
- Postgres generated full-text prefix ranking;
- authority, confidence, and recency.

Single-valued fields automatically supersede an older confirmed value when an
approved correction is added. This includes names, preferred address, creator
relationship, UID, server, account name, and main character.

Optional embeddings are intentionally not required. They should be introduced
only if evaluation demonstrates recall failures that structured and FTS5 lookup
cannot solve.

## Current data assumption

Current onboarding accepts only information the user deliberately approves for
Siduri to know. Game-account fields therefore use the normal private,
single-user Supabase memory path. Infrastructure credentials and API keys are
never memory records. A future local-only secret class is intentionally outside
this implementation.

## Operator surfaces

The Memory view separates:

- pending knowledge proposals;
- behavioral directives and their state;
- structured versioned claims;
- legacy compatibility memory.

Knowledge and runtime effects can be approved or rejected independently.
Confirmed directives can be disabled or revoked. The full memory reset remains
an explicit destructive operator action.

## Main implementation locations

| Responsibility | Location |
| --- | --- |
| Explicit teaching | `packages/memory/teaching.py` |
| Claim storage, retrieval, supersession, FTS5 | `packages/memory/service.py` |
| Active Self compilation and safety filtering | `packages/persona/behavior.py` |
| System/context prompt separation | `packages/persona/prompt.py` |
| Private chat orchestration | `apps/orchestrator/src/siduri_orchestrator/server.py` |
| Structured provider request boundary | `packages/model_router/router.py`, `packages/model_router/zai.py` |
| Guided teaching and inline approval | `apps/web/app/chat/chat-client.tsx` |
| Claim/directive inspection | `apps/web/app/operator/operator-client.tsx` |
| Deployment schema | `migrations/002_memory.sql` |
| Supabase runtime reliability | `packages/memory/postgres.py`, `docs/memory/SUPABASE_RUNTIME_RELIABILITY.md` |

The governing decisions are ADR 006, ADR 007, and ADR 008.

Supabase Postgres is authoritative and single-user. RLS blocks direct client
access; only the local orchestrator connects to memory. The old SQLite
file may be imported once with `scripts/migrate_sqlite_memory_to_supabase.py`;
there is no dual-write or SQLite runtime fallback.

## Verification evidence

The current implementation passes:

```bash
python -m unittest discover -s tests -v
npm run typecheck
npm run build
git diff --check
```

Relevant regressions cover deterministic extraction, orthogonal
relationship/behavior output,
provider system-role placement, scope filtering, injection resistance,
supersession, lexical retrieval, Postgres persistence, bounded unexpected HTTP
errors, and concurrent transaction-pooler-safe retrieval.

## Remaining work

The implemented path supports explicit private teaching in the local development
environment. Broader real-data onboarding remains gated on product hardening
tracked in `PLANS.md`:

- authenticated local API access before broader onboarding exposure;
- full correction, forget, export, and explain-memory UX for versioned claims;
- complete contradiction, abstention, poisoning, and temporal evaluation;
- optional semantic retrieval only if measured lexical misses justify it.

These remaining items do not change the central boundary: facts are retrieved
as context and approved behavior becomes Active Self.
