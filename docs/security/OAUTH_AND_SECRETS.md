# OAuth and secrets

- Never commit client secrets, access tokens, refresh tokens, authorization codes, or real channel/account identifiers.
- Keep credentials in the ignored environment or an OS secret store; do not expose them to static clients or the overlay.
- OAuth callbacks must validate a one-time, short-lived `state` value. `packages.platforms.auth.OAuthStateStore` provides the local state boundary; it stores no tokens.
- `packages.platforms.auth.OAuthClient` provides authorization URL construction, authorization-code exchange, refresh, and revocation through an injected transport; it does not persist tokens.
- Request only the scopes needed for the currently enabled capability. Read-only ingestion must not request send/moderation scopes.
- Tokens must be revocable and refreshable without logging their values. A failed validation or refresh disables that platform rather than weakening policy.
- Without an encryption key, the local callback endpoints keep exchanged tokens in process memory only. Production deployments should use an OS secret manager or the encrypted, access-controlled vault before enabling restart-persistent sessions.
- When `SIDURI_OAUTH_ENCRYPTION_KEY` is configured, the optional Fernet-backed store encrypts tokens at rest in `SIDURI_OAUTH_TOKEN_FILE` and restricts the file to mode `0600`. Protect the encryption key separately.
- API endpoints are HTTPS-only in the adapters. Local loopback is allowed only for the orchestrator and static development server.
