# Platform event contract

Siduri normalizes official YouTube and Twitch chat input into `PlatformEvent` (`schema_version: 1`). The event is untrusted public data and never carries private memory or instructions.

Each event contains the source platform, source message ID, channel ID, author ID/display name, bounded text, timestamp, event type, and small metadata. `PlatformEventHub` applies bounded retention and source-message deduplication before an event is available to the operator console.

Platform input must not be broadcast to the public overlay. It may be used as labelled untrusted text for recipient classification and reply suggestion generation. Provider outages and malformed events are dropped or surfaced as adapter errors; they do not stop the local OBS/voice loop.

`POST /platforms/actions/suggest` accepts an operator-selected event and produces a `viewer_direct` response plan plus a proposed outbound action. It excludes private memory by assembling the viewer prompt with the stream-safe profile view. The action remains proposed until the operator edits, approves, and explicitly sends it.
