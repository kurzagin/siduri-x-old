# OBS integration

Siduri's current OBS boundary is a local browser-source overlay connected to the orchestrator WebSocket. The overlay receives `response_plan` events plus `SpeechStarted`, `SpeechAmplitude`, `SpeechCompleted`, and `SubtitleFallback` events. It does not contain operator controls.

## Local setup

1. Start the orchestrator:

   ```bash
   SIDURI_AUDIO_ENABLED=true python -m apps.orchestrator.src.siduri_orchestrator.server
   ```

2. In OBS, create or select the stream scene.
3. Add a Browser Source pointing at the local file:

   ```text
   /home/zagin/Projects/kurzagin/siduri/apps/overlay/index.html
   ```

4. Enable transparent background and size the source for the Venus overlay.
5. Keep the operator console as a separate local browser window/source; never add it to the public scene.
6. Trigger a local response from the operator console or:

   ```bash
   curl -X POST http://127.0.0.1:8765/dev/mock-response
   ```

The overlay should show subtitles, transition from preparing to speaking, react to amplitude events, and return to idle. If local playback fails, subtitles remain visible and the overlay reports subtitle-only mode.

## Verified host state

On 2026-07-29, OBS Studio 32.1.2 was installed, the desktop exposed PipeWire/PulseAudio with a default analog sink, and direct VOICEVOX WAV playback through `ffplay` returned successfully. OBS scene creation and final stream routing remain operator-owned because scene names, capture layout, monitoring, and public audio routing are user-specific.

The code now contains a transport-neutral capture boundary in `packages/obs/capture.py`. It requires an explicit source name and an explicit local enable switch before requesting a still frame. Disconnected OBS, failed screenshots, and empty frames become safe results rather than exceptions; tests use `FakeObsTransport` and do not need OBS or Genshin.

The concrete OBS WebSocket v5 transport is implemented in `packages/obs/capture.py`. On 2026-07-30 it authenticated against the local OBS server, connected to source `genshin`, reported `streaming=false` and `recording=false`, and returned one still screenshot (231,934 bytes). The screenshot was not persisted or logged. Do not send the password in chat; it remains in the local ignored environment.

Pixel redaction rectangles can be configured locally with `SIDURI_OBS_REDACTION_RECTS=x,y,width,height;...`. They are applied in memory to supported PNG screenshots before the observation provider receives the frame.
