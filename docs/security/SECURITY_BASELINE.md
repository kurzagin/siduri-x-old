# Security baseline

Development binds to loopback. Secrets are excluded and `.env.example` contains placeholders only. Chat, OCR, web, and knowledge are untrusted. Events carry privacy classes; future outbound actions are audited and approval-gated. Document and implement capture, voice, and outbound kill switches before integration.
