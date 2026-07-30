# ADR 004: OBS as the default capture boundary

## Context

Screen capture must be bounded, operator-controlled, and compatible with OBS scenes without process-memory access or unofficial game clients.

## Decision

Use OBS WebSocket source screenshots, explicit capture enablement, in-memory redaction, expiring observations, and no raw-frame persistence.

## Consequences

The operator controls source and scene layout. The system inherits OBS availability but preserves a safe disabled/degraded mode.
