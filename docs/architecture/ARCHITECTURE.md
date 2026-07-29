# Architecture

The first architecture is a modular monolith: an async-shaped Python orchestrator owns session state and an in-process event bus; browser clients receive versioned events over a loopback WebSocket. Domain contracts are independent of provider names. PostgreSQL and local/R2 storage are behind interfaces.
