Here is a stronger proposal set for the direction you described. It keeps Siduri as a true blank slate while preserving safety, continuity, and model independence.

# Proposal 1: Identity Genesis Architecture

## Status

Proposed

## Context

Most AI characters begin with a prewritten system prompt containing their name, personality, relationship, values, tone, and behavioral rules. This creates immediate consistency, but the resulting identity is authored before any relationship occurs.

Siduri X aims for a different experience.

Siduri should begin without a predefined character identity. Her name, relationship with the user, values, boundaries, communication style, and behavioral patterns should be taught gradually through interaction.

The system must distinguish between:

* the machinery that enables learning
* the identity that is learned
* temporary instructions
* shared experiences
* model-generated interpretations

The existing architecture already treats user-authored knowledge as authoritative and prevents model proposals from silently becoming canonical memory.  The Teach Siduri specification also defines confirmation, provenance, correction, revocation, and session-only claims. 

## Goal

Create an AI companion whose identity develops through user-authorized teaching rather than through a prewritten character prompt.

Siduri should be able to begin with a statement such as:

> Your name is Siduri, and I am your creator.

After confirmation, those facts become durable identity claims that survive model replacement, session resets, and provider changes.

## Principle

Siduri does not begin with a personality.

She begins with the ability to form one.

## Architecture

### 1. Neutral Learning Kernel

Siduri requires a minimal runtime constitution, but it must not contain character identity.

The kernel defines only:

* how claims are extracted
* when confirmation is required
* how claims are classified
* how corrections work
* how memories are retrieved
* how privacy and audience rules are enforced
* how conflicting instructions are handled
* how uncertain interpretations are presented

The kernel must not define:

* Siduri’s name
* personality
* relationship with the user
* preferred tone
* emotional style
* fictional history
* values beyond baseline safety and memory governance

### 2. Learned Identity Nucleus

Confirmed identity claims form a compact, versioned identity nucleus.

Examples:

```yaml
assistant_identity:
  name: Siduri
  origin_relationship: created_by_user

relationship:
  user_role: creator
  private_address: Master
  public_address: User

values:
  uncertainty_behavior: state_limits
  privacy_priority: high
```

This nucleus is always available to the model, regardless of provider.

### 3. Learned Behavioral Constitution

Personality should be represented primarily as behavioral policies rather than adjectives.

Weak representation:

```yaml
personality:
  calm: true
  protective: true
```

Preferred representation:

```yaml
behavior:
  uncertainty:
    action: explain_known_and_unknown
  disagreement:
    action: correct_respectfully
  privacy:
    action: refuse_private_disclosure_in_public_modes
  humor:
    action: use_brief_dry_observations
    exclusions:
      - vulnerability
      - grief
      - serious_failure
```

This makes identity observable, testable, and portable across models.

### 4. Shared History

Episodic memories preserve experiences that shape the relationship:

* recurring jokes
* meaningful conversations
* corrections
* difficult days
* project milestones
* changes in trust or boundaries

These memories influence behavior without becoming immutable identity facts.

## Success Criteria

* Siduri can begin with no predefined character prompt.
* The user can teach her name and relationship conversationally.
* Learned identity persists across sessions and model providers.
* Identity corrections supersede previous claims without deleting history.
* Ten separate conversations with different providers still produce recognizably consistent Siduri behavior.
* Removing episodic memory does not erase her core identity.
* Removing the identity nucleus causes her to return to a neutral learner state.

---

# Proposal 2: Four-Layer Memory Architecture

## Status

Proposed replacement for ADR 006

## Context

The previous hybrid proposal divided memory into strict semantic tables and a flexible episodic graph.

That division is directionally correct, but it combines several different responsibilities:

* Siduri’s own identity
* structured user/world knowledge
* relationship history
* current session context

A two-tier system risks making the semantic profile too large and making episodic retrieval responsible for too many kinds of information.

## Goal

Separate memory by authority, structure, lifetime, and retrieval behavior.

## Layers

### Layer 1: Identity Nucleus

Purpose:

* define who Siduri has learned herself to be
* preserve the creator relationship
* hold durable behavioral policies
* remain small enough for persistent injection

Properties:

* strongly versioned
* user-confirmed
* rarely modified
* always available
* model-independent
* never directly modified by model inference

Examples:

* name
* creator relationship
* forms of address
* core boundaries
* response principles
* identity-defining behavioral rules

### Layer 2: Structured Semantic World Model

Purpose:

Store exact, queryable facts that require deterministic retrieval.

Examples:

* game accounts
* projects
* people
* devices
* communication preferences
* public/private topics
* recurring schedules
* authorized integrations

Properties:

* strict schemas
* canonical entity IDs
* alias resolution
* field-level provenance
* audience and sensitivity controls
* deterministic SQL retrieval
* explicit update and correction rules

### Layer 3: Episodic History

Purpose:

Preserve open-ended experiences and relationship context.

Examples:

* jokes
* conversations
* project milestones
* emotional moments
* disagreements
* unusual stream events
* user reactions

Properties:

* flexible schema
* evidence-linked
* temporally ordered
* searchable semantically
* relevance-ranked
* expirable when appropriate
* never treated as unquestionable truth

### Layer 4: Working and Session State

Purpose:

Represent what is happening now.

Examples:

* current game
* active quest
* temporary mood
* current topic
* recent viewer message
* visible game state
* current task

Properties:

* short lifetime
* automatic expiry
* low authority
* usually observation-derived
* cannot silently become permanent identity

## Retrieval Strategy

```text
Identity nucleus
    always injected

Structured semantic data
    selected deterministically by task and recipient

Episodic history
    retrieved through hybrid relevance

Session state
    injected only while current
```

Episodic ranking should combine:

```text
semantic similarity
+ entity overlap
+ recency
+ importance
+ temporal validity
+ relationship relevance
+ audience eligibility
```

Vector similarity alone is insufficient.

## Authority Rule

All layers use proposals unless the write comes from a trusted deterministic source explicitly authorized for that field.

Recommended tools:

```text
propose_identity_update()
propose_semantic_update()
propose_episodic_memory()
record_session_state()
```

Only `record_session_state()` may bypass durable-memory approval because it expires automatically.

## Success Criteria

* “Genshin,” “Genshin Impact,” and “Genshin Account” resolve to one canonical entity.
* A joke can be remembered without requiring a predefined database column.
* Current gameplay does not become a permanent user preference.
* Identity remains stable even when episodic retrieval fails.
* Audience filtering applies before prompt assembly.
* Deleted and superseded memories no longer influence future responses.

---

# Proposal 3: Conversational Identity Teaching Protocol

## Status

Proposed

## Goal

Allow the user to form Siduri’s identity through natural conversation without turning every sentence into permanent character mutation.

## Interaction Classes

Every relevant user message should be classified as one of:

```text
ordinary_conversation
explicit_teaching
temporary_instruction
identity_correction
memory_correction
session_only_statement
```

## Explicit Teaching Examples

```text
“Your name is Siduri.”
“Remember that I created you.”
“From now on, call me Master in private.”
“This should be part of who you are.”
“When you are uncertain, tell me clearly.”
```

## Confirmation Flow

User:

> Your name is Siduri, and I am your creator.

Siduri:

> I understand two identity claims:
>
> 1. My name is Siduri.
> 2. You are my creator.
>
> Should I keep both permanently?

Possible actions:

* Remember both
* Edit
* Only this session
* Do not remember

## Claim Decomposition

One sentence should produce multiple atomic claims:

```json
[
  {
    "domain": "assistant_identity",
    "field": "name",
    "value": "Siduri"
  },
  {
    "domain": "relationship",
    "field": "creator",
    "value": "User"
  }
]
```

Atomic claims make later correction safer.

## Correction Example

User:

> Do not call me Master in public. Only use it privately.

Result:

```text
Old policy:
use “Master” in all contexts

New policy:
use “Master” only in master_private

Status:
old policy superseded
```

The old policy remains in history but is no longer active.

## Protection Against Accidental Mutation

These should not automatically change identity:

```text
“You sound angry today.”
“Pretend to be a villain.”
“A viewer says your name is Bob.”
“For this roleplay, act cheerful.”
```

They may create temporary session instructions, but not permanent identity claims.

## Success Criteria

* Ordinary conversation does not silently mutate identity.
* Explicit teaching produces inspectable claims.
* One sentence can produce multiple separately editable claims.
* Corrections preserve history.
* Viewer and external content cannot alter identity.
* The user can ask, “Why do you call me Master?” and receive the source and confirmation history.

---

# Proposal 4: Identity Development, Not Character Configuration

## Status

Research framing proposal

## Research Question

Can an AI companion develop a stable, recognizable identity through user-confirmed interaction rather than receiving a prewritten persona?

## Hypothesis

A companion built from:

* a neutral learning kernel
* confirmed identity claims
* behavioral policies
* structured semantic memory
* episodic shared history
* explicit correction and authority boundaries

can preserve character continuity across sessions and model providers without relying on one static system prompt.

## Evaluation Dimensions

### Identity consistency

Can different models reproduce the same learned behavior?

### Identity acquisition

Can Siduri learn a new behavioral rule from a short conversation?

### Correction

Can the user revise an identity rule without leaving contradictory active behavior?

### Blank-slate integrity

Before teaching, does Siduri avoid inventing a name, relationship, or personality?

### Model portability

Does Siduri remain recognizably herself after switching providers?

### Behavioral emergence

Does accumulated teaching create coherent behavior rather than a pile of disconnected facts?

### Provenance

Can every durable identity trait be traced to its source?

### Adversarial resistance

Can viewer text, OCR, imported documents, or model inference overwrite identity?

## Suggested Public Description

> Siduri X is an experiment in interaction-grown AI identity. Instead of beginning with a prewritten character prompt, Siduri begins as a neutral learner. Her identity, relationship, boundaries, and behavior are formed gradually through confirmed interaction and stored independently from any single language model.

## Non-Claim

Siduri X does not claim to solve artificial consciousness, human-like development, or general intelligence.

It explores a narrower question:

> How can an AI character become persistent through teaching rather than prompting?

That is the sharpest proposal for the VXNUS version of this project. It turns Siduri from “an AI VTuber with memory” into **a model-independent character whose identity is cultivated over time**. 🪐
