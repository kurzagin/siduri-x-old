# Siduri implementation plan

## Current slice: Foundation and vertical-slice skeleton

- [x] Inspect the repository and local toolchain.
- [ ] Establish typed contracts, configuration, persistence boundaries, and ADRs.
- [ ] Implement a dependency-light local orchestrator with health/readiness/version endpoints and WebSocket broadcast.
- [ ] Implement the public overlay and private operator console shells.
- [ ] Add adapter interfaces, fake knowledge, migration, tests, and reproducible commands.
- [ ] Run the practical local checks and record limitations.

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

The next planned implementation is documented in `docs/CODEX_PROMPT_03_MODEL_AND_ADAPTERS.md`.

### Assumptions

- This repository starts empty apart from the supplied planning documents.
- Python 3.14 is acceptable for this dependency-light foundation; provider libraries will be compatibility-tested when introduced.
- A browser can open the static overlay and operator console directly. A future Vite build can replace the static server without changing the WebSocket contract.
- PostgreSQL is the target persistence engine, but no local database daemon is installed on this host; tests use an in-memory repository.
- The first response is a deterministic mock and contains no private Kur data.
