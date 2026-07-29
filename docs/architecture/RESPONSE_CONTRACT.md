# Response contract

`ResponsePlan` contains recipient, intent, semantic summary, `spoken_ja`, `subtitle_en`, `subtitle_id`, emotion, priority, interruptibility, evidence IDs, confidence, and approval requirement. The three renderings represent one semantic response. Later evaluation should compare named entities, numbers, uncertainty markers, and calls to action across all languages.

Phase 2 prompt assembly supplies the response planner with bounded identity, recipient, permitted memories, observations, and explicitly untrusted user/platform text sections.
