# Memory model

Memory classes are core identity, Me knowledge, preferences, relationship, episodic, session, and derived summaries. Items need provenance, confidence, sensitivity, allowed audiences, timestamps, expiry, supersession, correction, and deletion. `MemoryService` provides durable local SQLite CRUD, revision history, expiry, supersession, audience-filtered keyword retrieval, audit events, and proposal approval/rejection. PostgreSQL is the canonical deployment schema in `migrations/002_memory.sql`; install `siduri[postgres]` to use the optional adapter.

Memory writes use a two-stage authority boundary:

1. Siduri may infer a bounded `memory_proposals` list while answering private chat. Each candidate is stored separately as `pending` and is excluded from canonical retrieval.
2. The operator reviews the candidate in the local console and may edit, approve, or reject it. Approval creates a canonical `MemoryItem`; rejection or an unreviewed candidate never changes canonical memory.

The proposal retains provenance, sensitivity, and audience restrictions. Every proposal mutation is audit logged. Model output cannot directly create canonical memory.
