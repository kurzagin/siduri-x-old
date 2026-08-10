# Backup and restore

Use Supabase backups or `pg_dump` for Siduri memory. Back up the local encrypted
platform-token store, platform-action SQLite database, and operator-approved
configuration separately. Keep infrastructure credentials outside every
backup artifact. Do not back up raw screenshots, audio, or continuous
recordings. Test restore into a disposable Supabase project and verify claim
revisions, proposal state, and behavioral-directive continuity.
