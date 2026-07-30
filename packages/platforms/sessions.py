from __future__ import annotations

from dataclasses import dataclass
import json
import threading
from typing import Any

from .adapters import TwitchEventSubAdapter, YouTubeLiveChatAdapter
from .contracts import PlatformEvent, PlatformEventHub


@dataclass
class YouTubeLiveChatPoller:
    adapter: YouTubeLiveChatAdapter
    hub: PlatformEventHub
    live_chat_id: str | None = None
    next_page_token: str | None = None
    polling_interval_ms: int = 1000

    def poll_once(self) -> tuple[PlatformEvent, ...]:
        if self.live_chat_id is None:
            self.live_chat_id = self.adapter.find_active_live_chat()
        if self.live_chat_id is None:
            return ()
        events, self.next_page_token, interval = self.adapter.list_messages(self.live_chat_id, self.next_page_token)
        if interval is not None:
            self.polling_interval_ms = max(250, min(interval, 30_000))
        accepted = tuple(event for event in events if self.hub.ingest(event))
        return accepted


@dataclass
class TwitchEventSubSession:
    adapter: TwitchEventSubAdapter
    hub: PlatformEventHub
    broadcaster_user_id: str
    session_id: str | None = None
    subscription_id: str | None = None
    reconnect_url: str | None = None

    def handle_message(self, payload: dict[str, Any]) -> tuple[PlatformEvent, ...]:
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            return ()
        message_type = metadata.get("message_type")
        if message_type == "session_welcome":
            session = payload.get("payload", {}).get("session", {})
            if isinstance(session, dict) and isinstance(session.get("id"), str):
                self.session_id = session["id"]
                self.subscription_id = self.adapter.create_chat_subscription(self.broadcaster_user_id, self.session_id)
            return ()
        if message_type == "session_reconnect":
            session = payload.get("payload", {}).get("session", {})
            self.reconnect_url = session.get("reconnect_url") if isinstance(session, dict) else None
            return ()
        if message_type != "notification":
            return ()
        event = self.adapter.normalize_event(payload)
        if event is None or not self.hub.ingest(event):
            return ()
        return (event,)


class TwitchSocket:
    def recv(self) -> str | bytes: ...
    def close(self) -> None: ...


class TwitchSocketFactory:
    def connect(self, url: str) -> TwitchSocket: ...


class OptionalTwitchSocketFactory:
    """Uses websocket-client only when the optional platform extra is installed."""

    def connect(self, url: str) -> TwitchSocket:
        try:
            import websocket
        except ImportError as error:  # pragma: no cover - deployment-dependent
            raise RuntimeError("Twitch WebSocket support requires the platforms extra") from error
        return websocket.create_connection(url, timeout=30)


class TwitchEventSubRunner:
    def __init__(self, session: TwitchEventSubSession, socket_factory: TwitchSocketFactory, on_events: Any) -> None:
        self.session = session
        self.socket_factory = socket_factory
        self.on_events = on_events

    def run_once(self, url: str = "wss://eventsub.wss.twitch.tv/ws") -> str | None:
        socket = self.socket_factory.connect(url)
        try:
            while True:
                raw = socket.recv()
                if raw in (b"", ""):
                    raise ConnectionError("Twitch EventSub socket closed")
                payload = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
                events = self.session.handle_message(payload)
                if events:
                    self.on_events(events)
                if self.session.reconnect_url:
                    return self.session.reconnect_url
        finally:
            socket.close()

    def run_forever(self, stop_event: threading.Event, initial_url: str = "wss://eventsub.wss.twitch.tv/ws", retry_seconds: float = 2.0) -> None:
        url = initial_url
        while not stop_event.is_set():
            try:
                url = self.run_once(url) or initial_url
            except (ConnectionError, OSError, RuntimeError, ValueError):
                stop_event.wait(retry_seconds)


class YouTubeLiveChatRunner:
    def __init__(self, poller: YouTubeLiveChatPoller, on_events: Any) -> None:
        self.poller = poller
        self.on_events = on_events

    def run_forever(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            try:
                events = self.poller.poll_once()
                if events:
                    self.on_events(events)
            except (OSError, RuntimeError, ValueError):
                stop_event.wait(max(1.0, self.poller.polling_interval_ms / 1000))
            else:
                stop_event.wait(self.poller.polling_interval_ms / 1000)
