# Avatar state machine

The public overlay states are `idle`, `thinking/preparing`, `speaking`, and `subtitle-only`. `ResponsePlanCreated` enters preparing; `SpeechStarted` enters speaking; `SpeechAmplitude` changes animation intensity; `SpeechCompleted` or `SubtitleFallback` returns to idle. Unknown or malformed events leave the overlay safe and visually quiet.
