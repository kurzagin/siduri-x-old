# YouTube integration

Siduri uses the official YouTube Live Streaming API boundary. `YouTubeLiveChatAdapter.list_messages()` reads `liveChatMessages.list` with `part=snippet,authorDetails`, a live chat ID, and an optional page token. The adapter preserves the provider message ID for deduplication and normalizes text into `PlatformEvent`.

Sending uses the official `liveChatMessages.insert` shape, but the orchestrator only calls it through `OutboundActionService.send()` after an operator approval record exists. There is no automatic public reply path.

OAuth is intentionally not implemented in the browser. The orchestrator exposes loopback/HTTPS authorization start and callback routes with one-time state, and can use the encrypted token store when `SIDURI_OAUTH_ENCRYPTION_KEY` is configured. Least-privilege scopes and operator-controlled authorization remain required.

Relevant official references: [LiveChatMessages](https://developers.google.com/youtube/v3/live/docs/liveChatMessages) and [OAuth for web-server applications](https://developers.google.com/youtube/v3/guides/auth/server-side-web-apps).
