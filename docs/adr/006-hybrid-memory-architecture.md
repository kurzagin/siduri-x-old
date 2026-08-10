# ADR 006: Hybrid Memory Architecture

## Status
Proposed

## Context
Siduri currently relies on a single generic graph-like memory structure (`VersionedClaim` with Subject-Predicate-Value). While this offers high flexibility for forming broad, open-ended episodic memories, it struggles with reliability and deterministic retrieval. If the LLM slightly alters a subject name (e.g., "Genshin" vs "Genshin Account"), strict retrieval fails, and the agent's core identity becomes fragmented. 

Conversely, rigid database schemas (like Danna's expense tracker) offer 100% reliability and easy querying, but zero flexibility. An AI cannot organically remember a funny joke or a bad day if there isn't a strict database table for it.

Recent research in AI agents—specifically *AriGraph*, *Letta (MemGPT)*, and *Mem0*—highlights that a single memory paradigm is insufficient. Agents must mimic human cognitive structures by splitting memory into distinct tiers: Semantic (permanent facts) and Episodic (experiences/events).

## Goal
To implement a "Hybrid Memory Architecture" that gives Siduri the 100% deterministic reliability of strict relational tables (like Danna) for core identity, while preserving the infinite flexibility of the `VersionedClaim` graph for conversational episodic memory.

## Suggested Implementation

### 1. Dual-Tier Storage Model
The memory system should be split into two co-existing layers:
*   **Semantic Profile (Strict Tables):** Rock-solid, predefined database schemas for non-negotiable identity facts. For example: `GameAccounts` (game, uid, main_character) or `StreamBoundaries` (forbidden_topics). This guarantees that "Genshin Account" is never accidentally hallucinated as "Genshin".
*   **Episodic Graph (Flexible Graph):** The existing `VersionedClaim` database remains to capture open-ended conversation, jokes, and nuanced preferences.

### 2. Dual-Extraction Pipelines
The LLM should be provided with distinct tool contracts depending on the type of fact it is trying to learn:
*   `update_core_profile()`: Saves strict data directly to the Semantic tables.
*   `propose_episodic_memory()`: Sends vague or anecdotal data through the existing Operator Review queue as a `VersionedClaim`.

### 3. Asymmetric Retrieval (The Hybrid Loop)
Retrieval mechanisms must differ based on the tier:
*   **Persistent Injection (Semantic):** The Semantic Profile is fetched in its entirety (using simple SQL `SELECT`) and permanently injected into the prompt, similar to Danna's `memory_text` scratchpad. This guarantees 100% reliability for core facts.
*   **Vector Search (Episodic):** The Episodic Graph is fetched using a Vector Database (Embeddings) rather than a simple keyword match. This allows Siduri to do fuzzy, semantic matching (e.g., fetching a memory about "food" when asked about "lunch"). 

## References & Inspiration
*   **Letta (formerly MemGPT):** Uses an identical "Core Memory" (Persistent Scratchpad) + "Archival Memory" (Vector DB) architecture.
*   **AriGraph (Research):** Highlights the necessity of pairing structured Knowledge Graphs with chronological episodic memory for autonomous agents.
*   **Danna (Kur's Project):** Demonstrates the absolute reliability of highly-structured, queryable models (e.g., `expenses`) and persistent "scratchpad" injection.
