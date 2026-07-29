# Siduri implementation plan

## Current slice: Foundation and vertical-slice skeleton

- [x] Inspect the repository and local toolchain.
- [ ] Establish typed contracts, configuration, persistence boundaries, and ADRs.
- [ ] Implement a dependency-light local orchestrator with health/readiness/version endpoints and WebSocket broadcast.
- [ ] Implement the public overlay and private operator console shells.
- [ ] Add adapter interfaces, fake knowledge, migration, tests, and reproducible commands.
- [ ] Run the practical local checks and record limitations.

### Assumptions

- This repository starts empty apart from the supplied planning documents.
- Python 3.14 is acceptable for this dependency-light foundation; provider libraries will be compatibility-tested when introduced.
- A browser can open the static overlay and operator console directly. A future Vite build can replace the static server without changing the WebSocket contract.
- PostgreSQL is the target persistence engine, but no local database daemon is installed on this host; tests use an in-memory repository.
- The first response is a deterministic mock and contains no private Kur data.
