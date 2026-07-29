# Siduri

Siduri is Kur Zagin’s local-first Records Keeper and stream companion. This repository contains the Phase 0 and minimum Phase 1 foundation described in [`docs/CODEX_PROMPT_01_SIDURI_FOUNDATION.md`](docs/CODEX_PROMPT_01_SIDURI_FOUNDATION.md).

## Run the vertical slice

In one terminal:

```bash
python -m apps.orchestrator.src.siduri_orchestrator.server
```

Then open these files in a browser:

- `apps/overlay/index.html` — public transparent-style Venus overlay.
- `apps/operator_console/index.html` — local operator shell.

The operator console can trigger `POST /dev/mock-response`. The overlay reconnects to `ws://127.0.0.1:8765/ws` and displays the Japanese speech line plus English and Indonesian subtitles.

The operator console also exposes the Phase 2 local `Me` editor. The orchestrator provides `GET/PUT /me`, `GET/POST /memory`, and `GET/POST /memory/proposals` for testing audience-aware memory workflows. Local profile edits persist under ignored `data/me.json`; memory records persist under ignored `data/memory.sqlite3`. PostgreSQL deployment uses `migrations/002_memory.sql` and the optional `siduri[postgres]` adapter.

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

This slice intentionally uses only the Python standard library at runtime. `npm install` installs the pinned TypeScript toolchain for frontend checks. PostgreSQL, Docker/Podman, OBS, and VOICEVOX are optional at this stage; see `docs/operations/ARCH_LINUX_SETUP.md`.

The next-session handoff is [`docs/CODEX_PROMPT_03_MODEL_AND_ADAPTERS.md`](docs/CODEX_PROMPT_03_MODEL_AND_ADAPTERS.md).

To install the missing Arch Linux host tooling yourself, run:

```bash
./scripts/install_arch_foundation.sh
```

The script is manual and local-only. It installs packages, initializes PostgreSQL, enables the selected container runtime, and pulls the VOICEVOX Engine image without starting the Siduri stack. Use `--container-runtime podman` or `--container-runtime none` when appropriate.

## Boundaries

The domain depends on capabilities, not provider company names. The current server has an in-process event bus, mock model provider, fake knowledge source, in-memory repository, and explicit stubs for vision, TTS, OBS, platforms, and storage. See [`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md) and [`docs/adr/`](docs/adr/).
