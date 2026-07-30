# Twitch integration

Siduri uses official Twitch Helix and EventSub boundaries. `TwitchEventSubAdapter.normalize_event()` accepts `channel.chat.message` notifications from EventSub WebSocket or webhook transport and converts them to the normalized `PlatformEvent` contract.

Webhook signatures are checked with the Twitch HMAC construction and a bounded timestamp age. EventSub message IDs are deduplicated because Twitch may resend notifications. WebSocket session welcome, keepalive, and reconnect control messages are not treated as chat.

Sending uses the official Helix `chat/messages` shape and is reachable only through an approved `OutboundAction`. The Twitch client ID and access token remain environment-only.

The adapter can create a `channel.chat.message` WebSocket subscription after a valid EventSub session welcome. `TwitchEventSubRunner` owns reconnect URL handling and bounded retry; the actual socket client is an optional `websocket-client` extra. The orchestrator also exposes OAuth start/callback/refresh/revoke routes. See the official [EventSub WebSocket guidance](https://dev.twitch.tv/docs/eventsub/handling-websocket-events) and [OAuth token guidance](https://dev.twitch.tv/docs/authentication/getting-tokens-oauth).
