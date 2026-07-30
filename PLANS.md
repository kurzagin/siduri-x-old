# Siduri implementation plan

## Current slice: Foundation and vertical-slice skeleton

- [x] Inspect the repository and local toolchain.
- [x] Establish typed contracts, configuration, persistence boundaries, and ADRs.
- [x] Implement a dependency-light local orchestrator with health/readiness/version endpoints and WebSocket broadcast.
- [x] Implement the public overlay and private operator console shells.
- [x] Add adapter interfaces, fake knowledge, migration, tests, and reproducible commands.
- [x] Run the practical local checks and record limitations.

## Phase 2: Personality, relationship, and memory

- [x] Identity and relationship schemas.
- [x] Recipient classification and audience disclosure policy.
- [x] Dependency-free `Me` JSON importer and stream-safe projection.
- [x] Memory CRUD, revisions, retrieval, provenance, and approval-gated proposals.
- [x] Bounded prompt assembly with untrusted-text isolation.
- [x] Local operator editor and API endpoints for `Me`.
- [x] Personality/privacy evaluation tests.

Phase 2 uses durable local SQLite memory and persisted local `Me` data, with PostgreSQL schema/adapter preparation. Provider-independent model routing is present, and live GLM-5.2 use is now verified through the orchestrator.

## First model integration

- [x] Add provider-isolated GLM-5.2 adapter.
- [x] Keep API key environment-only.
- [x] Validate JSON response into `ResponsePlan`.
- [x] Preserve mock fallback and offline tests.
- [x] Run one live request after the operator configures `ZAI_API_KEY`.

The Prompt 03 implementation is documented in `docs/CODEX_PROMPT_03_MODEL_AND_ADAPTERS.md` and is complete below.

## Prompt 03: model and adapter hardening

- [x] Validate typed provider configuration and expose redacted readiness state.
- [x] Add capability routing, bounded transient retries, circuit cooldown, and degraded-mode responses.
- [x] Normalize and validate provider response plans before overlay broadcast.
- [x] Add privacy-safe request, failure, fallback, latency, and circuit telemetry.
- [x] Add vision, web-search, and tool-call contracts with local fakes.
- [x] Preserve credential-free mock operation and add failure/security regression tests.

Remaining Phase 3 polish is now covered: provider registry, a second model test double, provider usage/cost fields when returned, separated transport parsing, and hard timeout enforcement.

## Phase 4: local voice output

- [x] VOICEVOX health check and local endpoint validation.
- [x] Speaker/style discovery by metadata, including Nurse Robo Type T aliases.
- [x] Audio query and synthesis client with bounded speech input.
- [x] Priority queue, cancellation, synthesis latency, amplitude events, and subtitle-only fallback.
- [x] Add a gated local system playback sink (`ffplay`, `pw-play`, or `paplay`).
- [x] Emit overlay speech/amplitude events and drive preparing/speaking/idle animation states.
- [ ] Operator verification of the OBS browser source, scene layout, monitoring, and public audio route.

## E-Teyvat knowledge integration

- [x] Add the trusted E-Teyvat adapter at `https://eteyvat.krzgn.xyz`.
- [x] Preserve source URLs, dataset revisions, and preview status in results.
- [x] Support knowledge search, entity lookup, and deterministic farming retrieval.
- [x] Connect retrieved E-Teyvat evidence into the live response prompt.
- [x] Add operator-visible E-Teyvat citation display and evidence inspection.

The remaining operator step is to add the overlay browser source to the desired OBS scene and verify the stream-specific audio route. The orchestrator's local citation/evidence surfaces are implemented and covered by tests.

The current continuation is [`docs/CODEX_PROMPT_07_HANDOFF.md`](docs/CODEX_PROMPT_07_HANDOFF.md): authorize test platforms, start VOICEVOX, and complete operator-owned OBS/live-service verification.

## Current frontend migration

Phase 7 live-service verification is on hold because the current machine does not provide the game, OBS, VOICEVOX, or live platform environment. Frontend work continues locally in the Next.js app under `apps/web`:

- [x] Add Next.js 16 App Router shell and shared metadata/build configuration.
- [x] Migrate the private chat route to `/chat`.
- [x] Migrate the operator console route to `/operator`.
- [x] Migrate the OBS overlay route to `/overlay`.
- [x] Remove the legacy static HTML/JavaScript entrypoints after route parity review.
- [x] Redesign the operator console as a dashboard with status cards, tables, approval queues, and expandable technical details.
- [ ] Extract shared typed API/WebSocket client utilities and shared UI components.

## Phase 7: YouTube and Twitch platform boundary

- [x] Add versioned normalized platform event and outbound action contracts.
- [x] Add bounded deduplication and operator-only platform event inbox.
- [x] Add conservative viewer recipient selection and approval-gated reply suggestions.
- [x] Add official YouTube Live Chat discovery, ingestion, and approved-send adapter.
- [x] Add official Twitch EventSub normalization, signature verification, subscription, and approved-send adapter.
- [x] Add OAuth authorization URL, code exchange, refresh, revocation, one-time state, and optional encrypted token persistence.
- [x] Add operator-console review surfaces and audit-gated action endpoints.
- [x] Wire credentialed OAuth callback routing and long-lived YouTube polling/Twitch WebSocket session ownership.
- [ ] Run live provider verification with operator-approved test channels.

### Assumptions

- This repository starts empty apart from the supplied planning documents.
- Python 3.14 is acceptable for this dependency-light foundation; provider libraries will be compatibility-tested when introduced.
- A browser can open the static overlay and operator console directly. A future Vite build can replace the static server without changing the WebSocket contract.
- PostgreSQL is the target persistence engine, but no local database daemon is installed on this host; tests use an in-memory repository.
- The first response is a deterministic mock and contains no private Kur data.
