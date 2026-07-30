# Operations runbook

Start the orchestrator on loopback, serve `apps/`, check `/ready`, `/obs/health`, `/voice/health`, and `/platforms/status`, then verify the operator console before enabling any external worker. Keep platform ingestion disabled until OAuth and test-channel approval are complete. Use the emergency mute and token revocation runbooks for incidents.
