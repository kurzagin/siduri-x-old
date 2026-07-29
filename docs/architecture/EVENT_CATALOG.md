# Event catalog

All events use `EventEnvelope`: `event_id`, `event_type`, `schema_version`, `occurred_at`, `source`, `session_id`, `correlation_id`, `privacy_class`, and `payload`. Foundation events are `ResponsePlanCreated`; later events include `GameStateObserved`, `VoiceSynthesisCompleted`, `OverlayStateChanged`, and `OutboundActionProposed`.
