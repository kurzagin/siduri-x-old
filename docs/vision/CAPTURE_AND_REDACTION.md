# Capture and redaction

OBS capture is explicit, bounded, and kill-switchable. Frames are redacted in memory before vision, never returned to clients, persisted, or continuously recorded. Configured rectangles use `SIDURI_OBS_REDACTION_RECTS`; unsupported or malformed frames are rejected safely.
