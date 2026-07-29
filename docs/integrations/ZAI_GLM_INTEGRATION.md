# Z.AI GLM-5.2 integration

Siduri uses the provider-isolated `ZaiStructuredProvider`. It sends a bounded prompt to the Z.AI chat-completions endpoint, requests JSON mode, validates the returned `ResponsePlan`, and rejects malformed output. The API key is read from `ZAI_API_KEY`; it must never be committed or logged.

Configure locally, outside Git:

```bash
export SIDURI_MODEL_PROVIDER=zai
export SIDURI_MODEL_NAME=glm-5.2
export ZAI_API_KEY='your-key-here'
python -m apps.orchestrator.src.siduri_orchestrator.server
```

Alternatively, copy `.env.example` to `.env` and set `SIDURI_MODEL_PROVIDER=zai` and `ZAI_API_KEY` there. The orchestrator loads that local file without a third-party dependency. Explicit environment variables override `.env` values.

The default endpoint is `https://api.z.ai/api/paas/v4/chat/completions`. A configured key changes only the model provider; the mock provider remains available in tests and can be selected with `SIDURI_MODEL_PROVIDER=mock`.

The adapter currently uses non-streaming JSON responses, disables reasoning output for the response-planning call, applies a short timeout, and does not retry. Usage/cost telemetry and streaming are later hardening work.
