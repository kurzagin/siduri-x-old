# Codex Prompt 08 Handoff: Memory v2 Foundation & Frontend Cleanup

## Status

- **Frontend cleanup completed**: The Next.js frontend has had its typed API and WebSocket client utilities extracted into `apps/web/lib/api.ts`. Shared UI components like `EmptyState` were moved to `apps/web/components/`. All clients (`chat-client.tsx`, `operator-client.tsx`, `overlay-client.tsx`) have been updated to use these shared resources. This resolves the final pending frontend task in `PLANS.md`.
- **Memory v2 Contracts initiated**: We have started the implementation of Phase 2 (Memory v2: Teach Siduri). The versioned `SourceEvent` and `VersionedClaim` contracts (along with related Enums for Status, Authority, Confirmation, and Types) have been added to `apps/orchestrator/src/siduri_orchestrator/contracts.py`.

## Next Steps

The next session should continue following the `TEACH_SIDURI.md` rollout sequence:
1. **Implement temporal storage**: Update `data/memory.sqlite3` and `migrations/002_memory.sql` to support the new `VersionedClaim` append-only storage, lifecycle, and supersession mechanics.
2. **Teach Mode**: Add the private conversational Teach mode, providing inline confirmation receipts in the private `/chat` client rather than relying entirely on the operator console queue.
3. **Retrieval Upgrade**: Replace the basic keyword-only search in the response pipeline with the evidence-linked, temporal retrieval mechanism.

## Checks

Run `npm run typecheck` in the repository root to verify the frontend structural changes, and `python -m unittest discover -s tests -v` to ensure the new Python data classes have not broken the mock provider or event serialization expectations.
