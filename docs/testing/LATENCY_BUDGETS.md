# Latency budgets

Targets are: local health under 100 ms, fixture observation under 1 s, cached speech start under 500 ms, new short VOICEVOX synthesis under 2 s, and platform suggestion generation within the configured model timeout. Exceeding a target degrades to a bounded response or subtitle-only mode; it never bypasses approval.
