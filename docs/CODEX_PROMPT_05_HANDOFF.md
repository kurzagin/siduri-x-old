# Codex Prompt 05: Live Observation-to-Response Grounding

Use this handoff after [`CODEX_PROMPT_04_HANDOFF.md`](CODEX_PROMPT_04_HANDOFF.md).

## Verified baseline

- OBS WebSocket v5 connects to `ws://127.0.0.1:4455`.
- OBS source name is `genshin`.
- OBS authentication works through the ignored `.env`.
- `SIDURI_VISION_PROVIDER=zai` selects `glm-5v-turbo`.
- Three local fixtures exist under `assets/`; they are JPEGs despite two `.png` filenames.
- A live OBS screenshot reached GLM-5V and produced a normalized observation.
- The observation pipeline provides IDs, confidence, expiry, provider/model, OCR data, competing interpretations, deduplication, redaction hooks, and prompt formatting.
- The current live observation test proves perception only. It does not yet prove that Siduri uses the observation to form a grounded response.

## Start and verify

```bash
python -m unittest discover -s tests -v
npm run typecheck
npm run build
git diff --check
python -m apps.orchestrator.src.siduri_orchestrator.server
```

In another terminal:

```bash
curl http://127.0.0.1:8765/obs/health
curl -X POST http://127.0.0.1:8765/dev/observe-now
curl http://127.0.0.1:8765/observations
```

Observations expire after 30 seconds by design. Always trigger `observe-now` immediately before inspecting them.

## Mission

Complete the first real grounded response loop:

```text
OBS screenshot → GLM-5V observation → bounded E-Teyvat lookup
→ prompt assembly → validated ResponsePlan → subtitles/optional voice
```

The response must use the live observation's evidence ID, preserve its uncertainty, and avoid claiming more than the screenshot supports.

## Required work

1. Add a live `observe-and-respond` path using the active vision provider, not the fixture provider.
2. Select only current, non-expired observations for prompt assembly.
3. Resolve visible labels through E-Teyvat with bounded queries and preserve unresolved matches.
4. Attach observation and knowledge evidence IDs to the final `ResponsePlan`.
5. Make the Japanese, English, and Indonesian renderings semantically aligned.
6. Display source URL, revision, preview state, and correlation ID in the operator console.
7. Add tests proving a live-style observation changes the prompt and response evidence IDs.

## Safety boundaries

- Do not persist raw screenshots or continuous video.
- Do not add gameplay automation, memory reading, anti-cheat bypasses, or unofficial clients.
- Treat OCR and model output as untrusted data.
- Keep the current no-redaction policy explicit and operator-approved; do not silently generalize it to other accounts.
- Keep the provider contract model-agnostic. Do not put GLM-5V-specific assumptions into domain observation types.
- Public replies remain operator-approved.

## Completion criteria

- A live `observe-and-respond` request returns an evidence-linked `ResponsePlan`.
- The response is cautious when the observation confidence is low.
- E-Teyvat citations are visible to the operator.
- Expired observations cannot drive new responses.
- All repository checks pass.
