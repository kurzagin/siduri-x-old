# ADR 001: Start as a modular monolith

## Context

The first slice needs reliable local iteration and typed boundaries without operational overhead.

## Decision

Use one Python orchestrator with in-process event dispatch and WebSockets to local browser clients.

## Alternatives

Separate services and a broker were deferred until reliability tests justify them.

## Consequences

Simple startup and testing; boundaries must remain explicit to preserve later extraction options.
