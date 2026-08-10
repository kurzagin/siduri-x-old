# ADR 008: Separate Knowledge Claims from Runtime Effects

## Status

Accepted

## Context

Siduri must remember open-ended knowledge while also behaving consistently from
confirmed teaching. A single mutually exclusive category cannot represent both
responsibilities safely. A relationship statement may be factual, may affect
Siduri's persistent self, may authorize a scoped behavior, or may do all three.

Retrieval alone is insufficient for persistent behavior. A directive such as
"call the primary user Master in private" must remain active even when the next
message contains no related retrieval keywords. Conversely, ordinary facts and
game-account details must not become system instructions merely because they are
important.

## Decision

Siduri separates a teaching result into two independently reviewable outputs:

1. A canonical, atomic knowledge claim describing what is known.
2. Zero or more runtime effects describing how that claim affects Siduri.

Knowledge claims use a stable subject, predicate, and value with provenance,
authority, temporal state, sensitivity, and audience restrictions. Runtime
effects use one of these projection roles:

- `identity_context`
- `relationship_context`
- `behavioral_rule`

The knowledge domain and runtime effect are orthogonal. For example, a
relationship-domain claim may produce a behavioral rule without ceasing to be a
relationship claim.

Only confirmed runtime effects are compiled into the audience-scoped Active
Self. The provider adapter sends Active Self through the system role. Retrieved
claims, episodes, observations, external knowledge, platform text, and current
conversation remain in the bounded context role and cannot become system policy.

Explicit high-value private teaching is extracted deterministically for:

- Siduri's name;
- the primary user's name and creator relationship;
- scoped forms of address;
- Genshin UID, server, account name, and main character.

Deterministic extraction does not bypass review. It creates pending candidates
and preserves the private source event. The model may propose broader claims and
runtime effects under the same contracts.

## Consequences

- Siduri can query broad personal knowledge without injecting every fact as an
  instruction.
- Confirmed behavior persists across unrelated turns and model providers.
- A single sentence can produce both a relationship claim and a scoped behavior.
- Game-account claims are recipient-restricted. UID and account name are local
  secrets redacted from model-provider and E-Teyvat requests; server and main
  character are private context.
- Existing text memory remains a compatibility projection while versioned claims
  become the queryable authority.
- Hybrid full-text and semantic retrieval can be added without changing the
  Active Self boundary.
