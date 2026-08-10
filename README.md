# Siduri

Siduri is Kur Zagin’s Records Keeper and stream companion. Supabase Postgres is
the authoritative persistent memory backend; identity, relationship, and
behavior changes remain approval-gated.

The implemented conversational memory and learned-behavior flow is documented
in [`docs/memory/IMPLEMENTED_MEMORY_AND_BEHAVIOR.md`](docs/memory/IMPLEMENTED_MEMORY_AND_BEHAVIOR.md).
Supabase provisioning and one-time import are documented in
[`docs/memory/SUPABASE_SETUP.md`](docs/memory/SUPABASE_SETUP.md).
Connection pooling, timeout guarantees, and chat-failure troubleshooting are
documented in
[`docs/memory/SUPABASE_RUNTIME_RELIABILITY.md`](docs/memory/SUPABASE_RUNTIME_RELIABILITY.md).

## Run the vertical slice

Start the supervised local stack:

```bash
./start.sh
```

The script waits for both services to become healthy before reporting that
Siduri is ready. If either service exits, it stops the other one as well instead
of leaving a frontend that can only return 502 responses.

To run the services separately, use two terminals. In the first:

```bash
python -m apps.orchestrator.src.siduri_orchestrator.server
```

Then start the Next.js web client in the second:

```bash
npm run dev
```

Open `http://127.0.0.1:3000/chat`, `http://127.0.0.1:3000/operator`, or `http://127.0.0.1:3000/overlay`. The Next.js app in `apps/web` is the canonical frontend.

The operator console can trigger `POST /dev/mock-response`. The overlay reconnects to `ws://127.0.0.1:8765/ws`, displays the Japanese speech line plus English and Indonesian subtitles, and reacts to real VOICEVOX speech/amplitude events.

The `/operator` route is a local operations dashboard. Its Overview shows orchestrator, voice, OBS, and platform status; Memory, Evidence, and Platforms use structured review tables; Settings contains the local `Me` profile editor. Raw payloads are available only under expandable technical details. Approval-gated controls remain explicit for grounded responses, memory candidates, and outbound platform actions.

The operator console exposes separate review and inspection surfaces for pending
memory candidates, versioned claims, behavioral directives, and legacy memory
projections. Static `Me` profile authoring is deprecated in favor of private
conversational teaching. Candidates remain outside canonical memory and Active
Self until explicit approval. Memory records persist in single-user Supabase
Postgres tables defined by `migrations/002_memory.sql`. The orchestrator does
not dual-write or fall back to SQLite persistence. The former
`data/memory.sqlite3` file is only an optional one-time migration source.

Before starting Siduri, apply `migrations/002_memory.sql` to a Supabase project
and configure its pooled database URL as described in `.env.example`.
Install Python dependencies with:

```bash
python -m venv .venv
.venv/bin/pip install -e '.[platforms]'
```

The operator console also exposes fixture-first evidence inspection. `POST /dev/mock-observation` creates a synthetic, expiring observation; `GET /observations` lists retained observations and `GET /evidence` retrieves bounded E-Teyvat citation metadata. These fixtures are not live Genshin evidence and are intended to be replaced with configured screenshots later.

The private chat client uses `POST /chat` with the existing persona, private-memory policy, current observations, and configured model provider. Chat responses are returned to the private client only; they are not broadcast to the public overlay or sent to voice.

The platform boundary supports official YouTube Live Chat and Twitch EventSub normalization. `GET /platforms/status`, `GET /platforms/events`, and `GET /platforms/actions` are operator-console surfaces; `POST /platforms/actions` creates a suggestion, and approve/reject/send endpoints enforce the outbound action gate. Configure access tokens only through ignored environment variables. No platform sender is enabled unless its complete credential set is present.

For live platform workers, install the optional `siduri[platforms]` extra, configure OAuth credentials and an encryption key, then explicitly set `SIDURI_PLATFORM_INGEST_ENABLED=true`. YouTube polling and Twitch EventSub workers remain disabled by default.

With OBS configured and capture enabled, `POST /dev/observe-now` requests one in-memory still from the configured source and sends it through the bounded observation pipeline. The raw screenshot is neither returned nor persisted.

`POST /dev/mock-observe-response` exercises the complete fixture path from observation to evidence-linked response plan, subtitles, and optional voice.

## Enable GLM-5.2

The first real model adapter targets Z.AI GLM-5.2. Keep the API key outside Git and export it before starting the orchestrator:

```bash
export SIDURI_MODEL_PROVIDER=zai
export SIDURI_MODEL_NAME=glm-5.2
export ZAI_API_KEY='your-key-here'
python -m apps.orchestrator.src.siduri_orchestrator.server
```

For local development, you may instead copy `.env.example` to `.env`, fill in `ZAI_API_KEY`, and start the server normally. `.env` is ignored by Git, and explicit shell environment variables take precedence over values in the file.

Without `ZAI_API_KEY`, the orchestrator uses the deterministic mock provider. The adapter requests a validated JSON `ResponsePlan` and falls back to the mock provider if the Z.AI provider cannot be initialized.

## Checks

```bash
python -m unittest discover -s tests -v
npm run typecheck
npm run build
```

This slice intentionally uses only the Python standard library at runtime. `npm install` installs the pinned TypeScript toolchain for frontend checks. PostgreSQL and VOICEVOX remain optional; this host currently has OBS and PipeWire audio, while VOICEVOX must be started separately on `127.0.0.1:50021`. See [`docs/integrations/OBS_INTEGRATION.md`](docs/integrations/OBS_INTEGRATION.md) and [`docs/voice/VOICEVOX_INTEGRATION.md`](docs/voice/VOICEVOX_INTEGRATION.md).

Prompt 03 model reliability and Phase 4 voice integration are implemented: provider configuration is validated at startup, routing has bounded retries/cooldowns, structured responses are validated before broadcast, E-Teyvat evidence is available to the model, and telemetry is privacy-safe. The remaining manual step is adding the overlay browser source to the desired OBS scene.

The current-session handoff is [`docs/CODEX_PROMPT_07_HANDOFF.md`](docs/CODEX_PROMPT_07_HANDOFF.md). It covers the YouTube/Twitch OAuth and approval workflow, durable platform audit state, VOICEVOX/OBS verification, and the remaining operator-owned live gates.

To install the missing Arch Linux host tooling yourself, run:

```bash
./scripts/install_arch_foundation.sh
```

The script is manual and local-only. It installs packages, initializes PostgreSQL, enables the selected container runtime, and pulls the VOICEVOX Engine image without starting the Siduri stack. Use `--container-runtime podman` or `--container-runtime none` when appropriate.

## Boundaries

The domain depends on capabilities, not provider company names. The current server has an in-process event bus, mock model provider, fake knowledge source, in-memory repository, and explicit stubs for vision, TTS, OBS, platforms, and storage. See [`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md) and [`docs/adr/`](docs/adr/).
