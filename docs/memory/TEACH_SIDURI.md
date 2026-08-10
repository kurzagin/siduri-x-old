# Teach Siduri: conversational personal memory

## Status

Accepted specification. The claim/runtime-effect foundation, guided private
teaching, approval flow, Active Self compilation, structured retrieval, and
local-secret game-account handling are implemented. See
[`IMPLEMENTED_MEMORY_AND_BEHAVIOR.md`](IMPLEMENTED_MEMORY_AND_BEHAVIOR.md) for
the current behavior and verification evidence.

Automated and live-provider verification use fictional data. Personal values
must never be inferred from repository assets. Any local-development teaching
is an explicit user-operated action; broader real-data onboarding remains gated
by the privacy and security requirements below.

## Product intent

Kur should teach Siduri by talking to her, not by editing JSON. The teaching
experience should feel like a gradual relationship-building conversation while
remaining precise, inspectable, reversible, and privacy-aware.

Teach Siduri is not model fine-tuning. It is a controlled memory workflow that
extracts claims from conversation, asks for confirmation, stores approved claims
locally, and generates a current profile view when a response needs it.

## User experience

Teach mode is a private conversation with an explicit mode indicator. Siduri
asks one bounded question at a time and never treats an answer as permanent
memory merely because it sounds plausible.

Example:

> I play Genshin most evenings. I prefer exploration to difficult combat.

Siduri responds with a memory receipt:

> I found two possible memories: you often play Genshin in the evening, and you
> prefer exploration. Should I remember both?
>
> **Remember** · **Edit** · **Only this session** · **Do not remember**

The user can also use natural commands:

- “Teach me about …” starts a topic-guided teaching session.
- “What do you know about me?” shows confirmed claims with their sources.
- “Why do you believe that?” shows the supporting evidence and authority.
- “That is outdated” creates a correction rather than silently overwriting history.
- “Forget this” revokes the claim and removes it from future retrieval.
- “Keep this private” or “You may mention this on stream” sets audience policy.

Teach mode should ask for clarification when a statement is ambiguous, temporal,
or contradictory. It should not interrogate the user continuously; after a small
number of related claims it should offer to stop, change topic, or continue later.

## Memory layers

Siduri must keep these layers separate:

| Layer | Meaning | Default lifetime | Can become personal memory? |
| --- | --- | --- | --- |
| Conversation | Current user and assistant turns | Session | No, by itself |
| Evidence event | A bounded source observation, import, or explicit statement | Durable provenance | Only through claim review |
| Session state | What is happening now, such as the current game scene | Short-lived | No, unless explicitly promoted |
| Episodic memory | A dated event or experience | Durable or expiring | Yes, after confirmation |
| Semantic claim | A fact about the user, such as a hobby | Durable until corrected | Yes, after confirmation |
| Preference | A strength or constraint, such as “prefers exploration” | Durable, revisable | Yes, after confirmation |
| Behavioral rule | An instruction for Siduri's identity, relationship, or ongoing behavior | Durable, context-independent | Yes, after confirmation |
| Derived profile | A compact current view assembled from confirmed claims | Recomputable | Never authoritative |

The generated profile is a projection. It must be possible to delete or rebuild
it from the underlying claims and provenance.

## Claim lifecycle

Every candidate follows this lifecycle:

```text
source event -> extracted candidate -> pending confirmation
             -> confirmed | rejected | session-only
confirmed -> active -> superseded | expired | revoked
```

Model output, OCR, platform text, and external knowledge can create only
pending candidates. They cannot create active personal memory directly. Explicit
user corrections have the highest authority and create a new revision while
preserving the old claim for audit and explanation.

## Claim contract

The implementation should version a claim contract rather than storing an
unstructured biography. A claim needs at least:

```text
claim_id
schema_version
subject
predicate
value
claim_type                 semantic | preference | episodic | relationship
source_event_id
provenance
authority                  user_explicit | user_correction | import | repeated_dialogue | inference | observation
confidence
asserted_at
valid_from
valid_until
status                     pending | confirmed | rejected | session_only | superseded | revoked
sensitivity                public | stream_safe | private | secret
allowed_audiences
supersedes
replaces
user_confirmation         explicit | implied | none
```

The original source event must remain available to the local operator. A
summary may be shown to the model, but it must not replace the evidence record.

## Trust and conflict policy

When claims disagree, Siduri should prefer sources in this order:

1. A direct user correction.
2. A direct user statement explicitly offered for memory.
3. An official, user-authorised game-data import.
4. Repeated conversational evidence.
5. Siduri's inference.
6. OBS, OCR, public platform text, or other untrusted external input.

Conflicts must be represented as competing claims with time and provenance.
Siduri should say that the evidence conflicts or is incomplete instead of
choosing silently.

## Retrieval policy

Retrieval should be recipient-aware and evidence-first:

1. Generate candidates using exact/entity, full-text, and semantic retrieval.
2. Filter by recipient, sensitivity, audience, validity, and status.
3. Rerank using relevance, authority, confidence, recency, and temporal fit.
4. Resolve supersession and contradictions at retrieval time.
5. Supply a small evidence set and provenance to the response model.
6. Abstain or ask a question when the evidence is weak or conflicting.

Current retrieval combines deterministic subject/predicate lookup, weighted
lexical ranking, and Postgres full-text matching. Optional
semantic retrieval remains evaluation-driven future work.

## Game and hobby data

Hobbies and preferences should enter through Teach mode as user statements.
Game information should remain source-specific:

- a preference such as “I enjoy exploration” is a semantic claim;
- “I am playing Genshin tonight” is session state;
- an OBS reading is an expiring observation;
- account statistics require an official, explicitly authorised import.

No game credential, unofficial client, or raw screen recording may be used to
populate personal memory. Observed state must not silently become a claim about
the user's identity or enduring preferences.

## Privacy and security gates

Before real onboarding is enabled:

- the local operator API needs authentication and strict origin checks;
- memory writes need validation, size limits, audience checks, and audit events;
- personal memory should be stored locally and encrypted at rest;
- cloud model requests should contain only the minimum retrieved context;
- sensitive values should be redacted locally before any external request;
- every claim needs inspect, correct, export, expire, and delete operations;
- untrusted text must be labelled as data and cannot change memory policy;
- memory poisoning and prompt-injection regression tests are required.

## Evaluation gates

Use fictional users and scripted conversations to test:

- extracting explicit facts without inventing details;
- distinguishing permanent preferences from session state;
- confirmation, rejection, and “only this session” behaviour;
- temporal updates and supersession;
- contradictory evidence and correct abstention;
- audience filtering and public-output redaction;
- provenance explanations;
- correction, revocation, expiry, export, and deletion;
- malicious instructions embedded in OCR, platform text, or imported data.

The evaluation matrix should cover the five LongMemEval abilities: information
extraction, multi-session reasoning, temporal reasoning, knowledge updates, and
abstention.

## Rollout sequence

1. Keep real Me data absent; add only fictional fixtures.
2. Write and test the versioned claim and source-event contracts.
3. Implement local append-only storage and claim lifecycle operations.
4. Add the private Teach mode and inline memory receipts.
5. Add hybrid, temporal, evidence-linked retrieval.
6. Add the operator memory inspector and correction/forget flows.
7. Secure the local API and verify privacy gates.
8. Run the evaluation suite and only then enable real onboarding.

Current onboarding is limited to information the user approves for Siduri to
know. Account fields use ordinary single-user private memory. Infrastructure
credentials are not memory, and future local-only secret memory is a separate
phase.

The JSON Me document may remain as a generated compatibility export during the
migration, but it must not be the primary authoring surface or authority.
