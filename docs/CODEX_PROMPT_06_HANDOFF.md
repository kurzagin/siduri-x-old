# Codex Prompt 06: OBS Verification and Memory-Gated Siduri

Use this handoff from the repository root. Prompt 05's live observation-to-response implementation is present; the next session should verify the real OBS surface and continue hardening the private memory workflow.

## Current phase status

- Master Plan Phase 4, VOICEVOX: implemented with provider discovery, speech queue, amplitude events, and subtitle fallback.
- Master Plan Phase 5, Floating Venus and OBS: mostly implemented in code, but not exit-complete until the operator verifies the overlay as a Browser Source in the intended OBS scene and confirms audio/reconnect behavior.
- Master Plan Phase 6, Genshin eyes: the bounded screenshot → vision → E-Teyvat → response path is implemented and tested. Live OBS validation remains an operator-owned integration check.
- Memory authority: Siduri can propose isolated candidates, but only Master approval creates canonical memory.

## Verified implementation

- `POST /dev/observe-and-respond` captures a bounded observation, grounds it through E-Teyvat, and returns a staged evidence-linked `ResponsePlan`.
- Current observations expire and cannot drive new responses after expiry.
- Vision uses context/detail passes and an optional in-memory right-party crop. The active character is derived from the highlighted top party slot.
- Operator console exposes observations, citations, correlation IDs, response approval, Me profile editing, and pending memory candidates.
- Private chat is available at `apps/chat/` and uses private memory retrieval without public broadcast or voice output.
- Model plans may contain up to four `memory_proposals`; these are stored as `pending` in `memory_proposals`, never retrieved as canonical memory.
- Proposal review endpoints:
  - `GET /memory/proposals`
  - `POST /memory/proposals/update`
  - `POST /memory/proposals/approve`
  - `POST /memory/proposals/reject`
- Japanese frontend scripts are loaded as ES modules. This is required because TypeScript emits `export {}` to keep entrypoints isolated.

## Start and verify

From the repository root:

```bash
python -m unittest discover -s tests -v
npm run typecheck
npm run build
git diff --check
python -m apps.orchestrator.src.siduri_orchestrator.server
```

In a second terminal, serve the web clients from `apps`, not `apps/chat`:

```bash
python -m http.server 4173 --directory apps
```

Open:

- `http://127.0.0.1:4173/chat/`
- `http://127.0.0.1:4173/operator_console/`
- `apps/overlay/index.html` as the OBS Browser Source, or serve it from the same `apps` root.

Health checks:

```bash
curl http://127.0.0.1:8765/ready
curl http://127.0.0.1:8765/me
curl http://127.0.0.1:8765/memory/proposals
curl http://127.0.0.1:8765/obs/health
curl -X POST http://127.0.0.1:8765/dev/observe-and-respond
```

Observations expire by design. Trigger observation immediately before inspecting or responding to it.

## Next work

1. Add `apps/overlay/index.html` as a Browser Source in the intended OBS scene.
2. Verify transparent rendering, dimensions, reconnect behavior, and that debug/evidence data is not visible on the public overlay.
3. Verify `SpeechStarted`, `SpeechAmplitude`, `SpeechCompleted`, and subtitle fallback in OBS with audio enabled and disabled.
4. Use `apps/operator_console/index.html` to create and review a memory candidate from private chat. Confirm edit, approve, reject, audit, and canonical retrieval behavior.
5. Add endpoint-level tests for proposal update/approve/reject and persisted proposal state if the memory backend is expanded.
6. Keep public response approval separate from private chat and memory approval.

## Safety boundaries

- Never persist raw screenshots or continuous recordings.
- Do not add gameplay automation, process-memory reading, anti-cheat bypasses, or unofficial platform clients.
- Treat OCR, vision output, retrieved knowledge, and model-generated memory candidates as untrusted data.
- Do not expose private memory through stream recipients or public overlay content.
- Public outbound actions remain operator-approved.
- Do not commit secrets, real personal data, raw screen recordings, or account identifiers.

## Acceptance criteria

- All repository checks pass without cloud credentials.
- OBS displays the transparent overlay in the intended scene and reconnects safely.
- A live observation produces a cautious, evidence-linked response with aligned Japanese, English, and Indonesian text.
- Private chat can produce a pending memory candidate.
- Editing, rejection, and unreviewed candidates do not alter canonical memory.
- Approval creates canonical memory with provenance, sensitivity, audience restrictions, and audit history.
