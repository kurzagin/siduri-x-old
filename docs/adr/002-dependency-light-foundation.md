# ADR 002: Dependency-light local foundation

## Context

The inspected host has Python 3.14 and Node/npm; container and database access remain optional, while OBS is available for the local capture boundary.

## Decision

Use Python standard library for the runnable HTTP/WebSocket skeleton and TypeScript as the frontend check target. Pin TypeScript in npm.

## Alternatives

FastAPI/Vite/PostgreSQL containers are documented as the next integration baseline but are not prerequisites for this slice.

## Consequences

The slice runs immediately; production-grade HTTP/WebSocket behavior and database migrations still need hardening in Phase 2.
