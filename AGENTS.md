# Siduri contributor guide

## Commands

Use Python 3.14+ and the repository scripts:

```bash
python -m unittest discover -s tests -v
python -m apps.orchestrator.src.siduri_orchestrator.server
npm run typecheck
npm run build
```

The orchestrator binds to `127.0.0.1` by default. Do not add secrets, real personal data, unofficial platform clients, or raw screen recordings. Public outbound actions require operator approval.

Read `README.md`, `PLANS.md`, and the relevant ADR before changing boundaries or contracts. Keep event and response schemas versioned.
