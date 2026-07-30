# VOICEVOX integration

The local Phase 4 flow is health check → discover speaker/style metadata → identify Nurse Robo Type T by metadata → audio query → synthesis → priority queue/playback boundary → amplitude events. No permanent numeric style ID is stored: the style ID is resolved from `/speakers` at runtime. If the engine is unavailable, the speech service returns `subtitle_only` and invokes the subtitle fallback.

The default playback sink is intentionally null for safe tests. Set `SIDURI_AUDIO_ENABLED=true` to use the local `ffplay`, `pw-play`, or `paplay` command discovered on the host. The orchestrator emits speech and amplitude events to the overlay. OBS scene setup and final audio routing remain operator-owned. Attribution and applicable character terms must be completed before public streaming.

Run the optional local engine with:

```bash
docker compose --profile optional up voicevox
```

The orchestrator reports engine state at `GET /voice/health`. `SIDURI_VOICEVOX_ENABLED=true` enables voice dispatch; it defaults to enabled in the current local integration. `SIDURI_AUDIO_ENABLED=true` additionally enables system playback.

Verified on 2026-07-29: the running engine exposed Nurse Robo Type T with four styles, metadata discovery selected `ノーマル` dynamically, and a real Japanese synthesis returned 122,924 audio bytes in approximately 1.38 seconds. Direct `ffplay` playback also returned successfully.
