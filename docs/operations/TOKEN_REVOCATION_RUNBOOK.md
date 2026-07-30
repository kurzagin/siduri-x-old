# Token revocation runbook

1. Stop platform workers and disable outbound sending.
2. Use the provider console or the orchestrator revoke endpoint for the affected account.
3. Remove only the affected encrypted token entry; never print token values.
4. Rotate the client secret/encryption key if compromise is suspected.
5. Inspect audit metadata for attempted sends, then reauthorize with least privilege.
