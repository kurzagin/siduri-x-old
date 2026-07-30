from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .contracts import Platform, PlatformEvent, bounded_text, utc_now


class JsonTransport(Protocol):
    def request(self, method: str, url: str, *, headers: dict[str, str], body: bytes | None = None) -> dict[str, Any]: ...


class UrllibJsonTransport:
    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self.timeout_seconds = timeout_seconds

    def request(self, method: str, url: str, *, headers: dict[str, str], body: bytes | None = None) -> dict[str, Any]:
        request = Request(url, data=body, headers=headers, method=method)
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310 - endpoint is configuration-validated
            return json.loads(response.read().decode("utf-8"))


@dataclass(frozen=True)
class BearerCredentials:
    access_token: str
    client_id: str | None = None
    subject_id: str | None = None

    def headers(self) -> dict[str, str]:
        if not self.access_token.strip():
            raise ValueError("access token is empty")
        headers = {"Authorization": f"Bearer {self.access_token}"}
        if self.client_id:
            headers["Client-Id"] = self.client_id
        return headers


class YouTubeLiveChatAdapter:
    """Official YouTube Live Streaming API adapter for read and approved send."""

    def __init__(self, credentials: BearerCredentials, transport: JsonTransport | None = None, base_url: str = "https://www.googleapis.com/youtube/v3") -> None:
        self.credentials = credentials
        self.transport = transport or UrllibJsonTransport()
        if not base_url.startswith("https://"):
            raise ValueError("YouTube API endpoint must use HTTPS")
        self.base_url = base_url.rstrip("/")

    def list_messages(self, live_chat_id: str, page_token: str | None = None) -> tuple[tuple[PlatformEvent, ...], str | None, int | None]:
        params = {"liveChatId": bounded_text(live_chat_id, field_name="live_chat_id", limit=256), "part": "snippet,authorDetails"}
        if page_token:
            params["pageToken"] = bounded_text(page_token, field_name="page_token", limit=512)
        payload = self.transport.request("GET", f"{self.base_url}/liveChat/messages?{urlencode(params)}", headers=self.credentials.headers())
        events: list[PlatformEvent] = []
        for item in payload.get("items", []):
            event = self._event_from_item(item, live_chat_id)
            if event is not None:
                events.append(event)
        interval = payload.get("pollingIntervalMillis")
        return tuple(events), payload.get("nextPageToken"), interval if isinstance(interval, int) else None

    def find_active_live_chat(self) -> str | None:
        payload = self.transport.request(
            "GET", f"{self.base_url}/liveBroadcasts?{urlencode({'part': 'snippet,status', 'broadcastStatus': 'active', 'mine': 'true'})}",
            headers=self.credentials.headers(),
        )
        for item in payload.get("items", []):
            if isinstance(item, dict):
                snippet = item.get("snippet")
                if isinstance(snippet, dict) and isinstance(snippet.get("liveChatId"), str):
                    return snippet["liveChatId"]
        return None

    def _event_from_item(self, item: object, live_chat_id: str) -> PlatformEvent | None:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            return None
        snippet = item.get("snippet")
        author = item.get("authorDetails")
        if not isinstance(snippet, dict) or not isinstance(author, dict):
            return None
        message = snippet.get("displayMessage") or snippet.get("textMessageDetails", {}).get("messageText")
        if not isinstance(message, str) or not message.strip():
            return None
        return PlatformEvent(
            platform=Platform.YOUTUBE,
            event_type="chat_message",
            source_message_id=item["id"],
            channel_id=live_chat_id,
            author_id=str(snippet.get("authorChannelId", author.get("channelId", "unknown"))),
            author_display_name=str(author.get("displayName", "unknown")),
            text=message,
            occurred_at=str(snippet.get("publishedAt", utc_now())),
            metadata={"message_type": str(snippet.get("type", "unknown"))},
        )

    def send_message(self, target_id: str, text: str) -> str:
        body = json.dumps({"snippet": {"liveChatId": bounded_text(target_id, field_name="live_chat_id", limit=256), "type": "textMessageEvent", "textMessageDetails": {"messageText": bounded_text(text, field_name="text", limit=2000)}}}).encode()
        payload = self.transport.request("POST", f"{self.base_url}/liveChat/messages?part=snippet", headers={**self.credentials.headers(), "Content-Type": "application/json"}, body=body)
        message_id = payload.get("id")
        if not isinstance(message_id, str):
            raise ValueError("YouTube send response did not contain a message ID")
        return message_id

def verify_twitch_eventsub_signature(message_id: str, timestamp: str, body: bytes, signature: str, secret: str, *, now: float | None = None, max_age_seconds: int = 600) -> bool:
    if not message_id or not timestamp or not signature or len(secret) < 10:
        return False
    try:
        event_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return False
    if abs((time.time() if now is None else now) - event_time) > max_age_seconds:
        return False
    digest = hmac.new(secret.encode("ascii"), message_id.encode() + timestamp.encode() + body, hashlib.sha256).hexdigest()
    expected = "sha256=" + digest
    return hmac.compare_digest(expected, signature)


class TwitchEventSubAdapter:
    """Normalizes official Twitch EventSub WebSocket or webhook notifications."""

    def __init__(self, credentials: BearerCredentials, transport: JsonTransport | None = None, base_url: str = "https://api.twitch.tv/helix") -> None:
        self.credentials = credentials
        self.transport = transport or UrllibJsonTransport()
        if not credentials.client_id:
            raise ValueError("Twitch requires a client ID")
        if not base_url.startswith("https://"):
            raise ValueError("Twitch API endpoint must use HTTPS")
        self.base_url = base_url.rstrip("/")

    @staticmethod
    def normalize_event(payload: dict[str, Any], *, received_at: str | None = None) -> PlatformEvent | None:
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict) or metadata.get("message_type") != "notification":
            return None
        inner = payload.get("payload")
        if not isinstance(inner, dict) or inner.get("subscription", {}).get("type") != "channel.chat.message":
            return None
        event = inner.get("event")
        if not isinstance(event, dict):
            return None
        message = event.get("message", {})
        text = message.get("text") if isinstance(message, dict) else None
        if not isinstance(text, str) or not text.strip():
            return None
        return PlatformEvent(
            platform=Platform.TWITCH,
            event_type="chat_message",
            source_message_id=str(event.get("message_id") or metadata.get("message_id")),
            channel_id=str(event.get("broadcaster_user_id", "unknown")),
            author_id=str(event.get("chatter_user_id", "unknown")),
            author_display_name=str(event.get("chatter_user_name", "unknown")),
            text=text,
            occurred_at=str(received_at or metadata.get("message_timestamp") or utc_now()),
            metadata={"subscription_type": "channel.chat.message", "channel_login": str(event.get("broadcaster_user_login", ""))},
        )

    def create_chat_subscription(self, broadcaster_user_id: str, session_id: str) -> str:
        if not self.credentials.subject_id:
            raise ValueError("Twitch EventSub requires the authenticated user ID")
        body = json.dumps({
            "type": "channel.chat.message", "version": "1",
            "condition": {"broadcaster_user_id": bounded_text(broadcaster_user_id, field_name="broadcaster_user_id", limit=256), "user_id": self.credentials.subject_id},
            "transport": {"method": "websocket", "session_id": bounded_text(session_id, field_name="session_id", limit=256)},
        }).encode()
        payload = self.transport.request("POST", f"{self.base_url}/eventsub/subscriptions", headers={**self.credentials.headers(), "Content-Type": "application/json"}, body=body)
        data = payload.get("data")
        if not isinstance(data, list) or not data or not isinstance(data[0], dict) or not isinstance(data[0].get("id"), str):
            raise ValueError("Twitch subscription response did not contain a subscription ID")
        return data[0]["id"]

    def send_message(self, target_id: str, text: str) -> str:
        body = json.dumps({"broadcaster_id": bounded_text(target_id, field_name="broadcaster_id", limit=256), "sender_id": bounded_text(self.credentials.subject_id or "", field_name="sender_id", limit=256), "message": bounded_text(text, field_name="text", limit=500)}).encode()
        payload = self.transport.request("POST", f"{self.base_url}/chat/messages", headers={**self.credentials.headers(), "Content-Type": "application/json"}, body=body)
        data = payload.get("data")
        if not isinstance(data, list) or not data or not isinstance(data[0], dict) or not isinstance(data[0].get("message_id"), str):
            raise ValueError("Twitch send response did not contain a message ID")
        return data[0]["message_id"]
