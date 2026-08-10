# Codex Prompt 09 Handoff: Memory v2 Temporal Storage & Teach Mode

## Status

- **Temporal Storage Implemented**: `packages/memory/service.py` and `migrations/002_memory.sql` have been updated with `VersionedClaim` and `SourceEvent` tables. The new claim lifecycle now allows appending immutable temporal claims.
- **Conversational Teach Mode Added**: The Next.js frontend (`apps/web/app/chat/chat-client.tsx`) now supports parsing memory proposals returned by the backend and rendering them as inline confirmation receipts. The user can interactively click "Approve" or "Reject".
- **Retrieval Upgrade (Evidence-Linked)**: `MemoryService` now includes `retrieve_claims()` which evaluates claims based on their `valid_from` and `valid_until` properties, as well as `allowed_audiences` and `supersedes` links. The `PromptAssembler` has been updated to serialize `VersionedClaim` objects for the LLM.

## Next Steps

With the core claim storage and teach-mode lifecycle operational, the remaining tasks for Memory v2 are:

1. **Memory Inspector UI**: Build a UI tool (likely within the operator console) to inspect all active/superseded memory claims, view their provenance (SourceEvents), and manually export, edit, or delete claims.
2. **Security Gates**: Complete local API authentication and strict origin checks to prevent unauthorized access before onboarding any real profile data.
3. **Fictional Evaluation Suite**: Construct a set of fictional JSON dialogues (fixtures) to test whether the system extracts facts correctly, handles contradictory claims, properly respects "only this session", and maintains temporal tracking correctly.

Run `npm run typecheck` in the root and `python -m unittest discover -s tests -v` to ensure everything remains green before continuing.
