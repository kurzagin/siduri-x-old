# Emergency mute runbook

1. Disable `SIDURI_AUDIO_ENABLED` and `SIDURI_VOICEVOX_ENABLED`, or stop the orchestrator.
2. Disable OBS monitoring/public audio and hide or remove the Browser Source if needed.
3. Set `SIDURI_OBS_CAPTURE_ENABLED=false` to stop new captures.
4. For public platform risk, stop platform workers and revoke platform tokens.
5. Preserve only bounded audit metadata; do not record or retain raw screen/audio streams.
