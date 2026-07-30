# Audio routing architecture

Response plan → speech queue → VOICEVOX synthesis → selected local playback sink → OBS audio capture/monitoring. The overlay receives speech lifecycle and amplitude events separately. A null sink and subtitle fallback are valid degraded modes. Public audio is disabled unless the operator explicitly enables `SIDURI_AUDIO_ENABLED` and verifies the OBS monitoring route.
