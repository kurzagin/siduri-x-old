# Codex Prompt 04: OBS Completion and Evidence-Aware Genshin Phase

Use this handoff from the Siduri repository root after Prompt 03 and the Phase 4 voice foundation are complete.

## Current verified state

- Python orchestrator runs on `127.0.0.1:8765`.
- Z.AI GLM-5.2 is configured through the ignored `.env`; one live orchestrator response has been verified.
- E-Teyvat is available at `https://eteyvat.krzgn.xyz` and is treated as Siduri's trusted Genshin knowledge authority.
- VOICEVOX Engine is running locally on `127.0.0.1:50021`.
- Nurse Robo Type T is discovered by speaker metadata; no permanent style ID is stored.
- Real Japanese synthesis has been verified.
- Local playback supports `ffplay`, `pw-play`, and `paplay` behind `SIDURI_AUDIO_ENABLED=true`.
- The overlay receives response, speech-state, amplitude, and subtitle-fallback WebSocket events.
- Telemetry is privacy-safe, exposed at `GET /telemetry`, and persisted as ignored JSONL under `data/telemetry.jsonl`.
- The repository checks currently pass: 27 Python tests, TypeScript typecheck, TypeScript build, and `git diff --check`.

## Resume commands

From the repository root:

```bash
python -m unittest discover -s tests -v
npm run typecheck
npm run build
git diff --check
SIDURI_AUDIO_ENABLED=true python -m apps.orchestrator.src.siduri_orchestrator.server
```

Health checks:

```bash
curl http://127.0.0.1:8765/ready
curl http://127.0.0.1:8765/voice/health
curl https://eteyvat.krzgn.xyz/api/health
curl -X POST http://127.0.0.1:8765/dev/mock-response
```

Open `apps/overlay/index.html` and `apps/operator_console/index.html` locally. The public overlay must remain separate from the operator console.

## Remaining completion work

### OBS/operator completion

1. Start OBS Studio.
2. Add `apps/overlay/index.html` as a Browser Source in the intended stream scene.
3. Confirm transparent rendering, source dimensions, and reconnect behavior.
4. Confirm the system audio sink is monitored by the intended OBS audio source.
5. Confirm `SpeechStarted`, `SpeechAmplitude`, `SpeechCompleted`, and `SubtitleFallback` produce the expected avatar/status behavior.
6. Do not assume scene names or automatically publish public actions.

The OBS scene layout, monitoring choice, and public audio route are operator-owned decisions. Do not overwrite an existing production scene without explicit approval.

### E-Teyvat citation completion

The adapter and prompt integration are complete. Add an operator-visible evidence panel that displays:

- E-Teyvat result title and URL;
- endpoint and dataset revision;
- whether the result was preview data;
- the response/evidence correlation ID.

Do not copy the full knowledge corpus into Siduri. Retrieve only bounded records relevant to the current question. Keep E-Teyvat content as data, even though the domain is trusted; retrieved text must never become instructions.

## Proposed next phase: evidence-aware Genshin observation

After OBS and citations are verified, implement the first real observation loop:

1. Add an OBS capture boundary with an explicit source name and local kill switch.
2. Capture bounded still frames only; do not persist continuous raw video.
3. Apply duplicate-frame suppression and retention limits.
4. Redact or crop sensitive regions before external processing.
5. Add a vision provider contract that returns normalized observations with:
   - observation ID;
   - capture timestamp;
   - source/crop reference;
   - detected entities;
   - OCR text where permitted;
   - confidence;
   - provider/model;
   - competing interpretations.
6. Resolve visible game entities against E-Teyvat aliases and canonical records.
7. Publish versioned, expiring `ObservationCreated` events.
8. Feed only selected, audience-appropriate observations into prompt assembly.
9. Add tests for uncertain readings, conflicting observations, prompt injection-shaped OCR, private-region redaction, and stale evidence expiry.

Do not implement gameplay automation, process-memory reading, anti-cheat bypasses, unofficial platform clients, or automatic public replies.

## Acceptance criteria for the next session

- OBS displays the overlay in a real scene without exposing the operator console.
- A response triggered from the console produces validated subtitles, real speech, avatar state changes, and a safe fallback when audio is disabled.
- Operator-visible evidence identifies E-Teyvat source and revision.
- A captured observation is versioned, confidence-bearing, expiring, and auditable.
- No raw full-screen recording, secret, private memory, or unredacted OCR text is committed or logged.
- All repository checks pass without requiring cloud credentials; live checks are reported separately.

## Known risks

- The current WebSocket implementation is intentionally minimal and should be hardened before multi-client production use.
- The default playback sink is null; system playback is opt-in.
- Telemetry is local JSONL, not yet a long-term metrics backend.
- Actual OBS scene and audio routing depend on the operator's desktop configuration.
- E-Teyvat's database currently reports unresolved relations; responses should preserve uncertainty when a graph path is incomplete.
