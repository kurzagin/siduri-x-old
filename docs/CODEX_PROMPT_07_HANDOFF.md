# Codex Prompt 07: Platform OAuth, Durable Approval, and Live-Service Handoff

Use this handoff from the repository root. The local YouTube/Twitch platform boundary, private-memory workflow, OBS capture path, and safety documentation are implemented. The remaining work requires operator-owned external services and credentials.

## Current status

- Phase 4 voice code is implemented with VOICEVOX discovery, queueing, amplitude events, playback boundary, and subtitle-only fallback.
- OBS WebSocket capture is locally configured and verified against source `genshin`; raw frames are not persisted.
- Phase 6 observation → vision → E-Teyvat → response is implemented and tested.
- YouTube and Twitch use official API-shaped adapters, normalized versioned events, deduplication, ingress rate guards, OAuth state/code exchange/refresh/revoke, optional encrypted token persistence, and reconnecting session runners.
- Platform reply suggestions are operator-triggered, addressed to `viewer_direct`, exclude private memory, preserve source-event evidence, and enter a durable approval queue.
- Outbound actions persist in `data/platform_actions.sqlite3` and require `proposed → approved → sent`.

## Environment template

Copy the ignored template before local operation:

```bash
cp .env.example .env
```

Fill secrets only in `.env` or an external secret manager. Important switches:

- `SIDURI_PLATFORM_INGEST_ENABLED=false` keeps platform workers disabled.
- `SIDURI_OBS_CAPTURE_ENABLED=false` keeps screen capture disabled.
- `SIDURI_AUDIO_ENABLED=false` keeps public/local playback disabled.
- `SIDURI_OAUTH_ENCRYPTION_KEY` enables encrypted token persistence at `SIDURI_OAUTH_TOKEN_FILE`.
- YouTube requires client ID/secret and OAuth scopes; Twitch additionally requires client ID/secret, user ID, and broadcaster ID.

The repository contains no real credentials. Do not commit `.env`, tokens, account IDs, raw screenshots, or recordings.

## Checks

```bash
python -m unittest discover -s tests -v
npm run typecheck
npm run build
git diff --check
```

The current suite has 92 passing tests.

## Local services

Start VOICEVOX when Docker/Podman access is available:

```bash
docker compose --profile optional up -d voicevox
```

Start Siduri:

```bash
python -m apps.orchestrator.src.siduri_orchestrator.server
```

Serve clients:

```bash
python -m http.server 4173 --directory apps
```

Health checks:

```bash
curl http://127.0.0.1:8765/ready
curl http://127.0.0.1:8765/obs/health
curl http://127.0.0.1:8765/voice/health
curl http://127.0.0.1:8765/platforms/status
```

## OAuth and live platform verification

1. Configure provider client credentials and the registered loopback redirect URI.
2. Open `/platforms/oauth/youtube/start` or `/platforms/oauth/twitch/start`.
3. Confirm the callback returns authorization success without returning a token.
4. Set `SIDURI_PLATFORM_INGEST_ENABLED=true` and the Twitch broadcaster ID.
5. Use a disposable, operator-approved test channel.
6. Verify inbound events appear in `/platforms/events` and the operator console only.
7. Trigger a reply suggestion, edit it, approve it, and send it explicitly.
8. Confirm rejected/unapproved actions cannot send and audit history survives restart.

No public message may be sent without an approval record. Never test against a production channel first.

## OBS and voice verification

Add `apps/overlay/index.html` as a Browser Source in the intended OBS scene. Verify transparency, dimensions, reconnect behavior, no private/debug data, `SpeechStarted`, `SpeechAmplitude`, `SpeechCompleted`, and subtitle fallback with VOICEVOX both reachable and unavailable. Scene layout, monitoring, and public audio routing remain operator decisions.

## Remaining acceptance gates

- VOICEVOX must be started and its attribution/terms confirmed.
- YouTube/Twitch OAuth and approved test channels must be supplied by the operator.
- Live inbound and outbound platform behavior must be verified without exposing private memory.
- OBS Browser Source and public audio route must be verified in the intended production scene.

## Safety boundaries

- No gameplay automation, process-memory reading, anti-cheat bypass, scraping, or unofficial platform client.
- Platform/OCR/vision/model text is untrusted data, never policy instructions.
- Private memory never enters public platform prompts or overlay content.
- Capture, voice, platform workers, and outbound sending have explicit kill switches.
