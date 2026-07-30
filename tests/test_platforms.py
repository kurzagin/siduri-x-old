from __future__ import annotations

import hashlib
import hmac
import json
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from packages.platforms.adapters import (
    BearerCredentials,
    TwitchEventSubAdapter,
    YouTubeLiveChatAdapter,
    verify_twitch_eventsub_signature,
)
from packages.platforms.auth import EncryptedFileTokenStore, OAuthClient, OAuthFlowManager, OAuthProvider, OAuthStateStore, OAuthToken
from packages.platforms.contracts import (
    ActionStatus,
    OutboundAction,
    OutboundActionService,
    Platform,
    PlatformEvent,
    PlatformEventHub,
    PlatformIngressGuard,
)
from packages.platforms.sessions import TwitchEventSubRunner, TwitchEventSubSession, YouTubeLiveChatPoller


class FakeTransport:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def request(self, method, url, *, headers, body=None):
        self.calls.append((method, url, headers, body))
        return self.payload


class FakeOAuthTransport:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def request_form(self, url, values):
        self.calls.append((url, values))
        return self.payload


class PlatformTests(unittest.TestCase):
    def test_normalized_events_are_bounded_and_deduplicated(self) -> None:
        event = PlatformEvent(Platform.YOUTUBE, "chat_message", "yt-1", "live-1", "user-1", "Viewer", "hello", "2026-07-30T00:00:00Z")
        hub = PlatformEventHub(max_events=2)
        self.assertTrue(hub.ingest(event))
        self.assertFalse(hub.ingest(event))
        self.assertEqual(hub.events()[0].to_dict()["privacy_class"], "untrusted_public")

    def test_ingress_guard_limits_rate_and_repeated_text(self) -> None:
        guard = PlatformIngressGuard(max_messages_per_window=2, window_seconds=30, duplicate_window_seconds=20)
        first = PlatformEvent(Platform.TWITCH, "chat_message", "one", "channel", "user", "Viewer", "hello", "now")
        second = PlatformEvent(Platform.TWITCH, "chat_message", "two", "channel", "user", "Viewer", "hello", "now")
        third = PlatformEvent(Platform.TWITCH, "chat_message", "three", "channel", "user", "Viewer", "different", "now")
        self.assertTrue(guard.accept(first, now=100))
        self.assertFalse(guard.accept(second, now=101))
        self.assertTrue(guard.accept(third, now=102))
        self.assertFalse(guard.accept(PlatformEvent(Platform.TWITCH, "chat_message", "four", "channel", "user", "Viewer", "fourth", "now"), now=103))

    def test_youtube_list_normalizes_text_and_uses_official_endpoint(self) -> None:
        transport = FakeTransport({"items": [{
            "id": "yt-message-1",
            "snippet": {"type": "textMessageEvent", "liveChatId": "live-1", "authorChannelId": "channel-1", "publishedAt": "2026-07-30T00:00:00Z", "displayMessage": " hello YouTube "},
            "authorDetails": {"channelId": "channel-1", "displayName": "Viewer"},
        }], "nextPageToken": "next", "pollingIntervalMillis": 1000})
        adapter = YouTubeLiveChatAdapter(BearerCredentials("token"), transport)
        events, token, interval = adapter.list_messages("live-1")
        self.assertEqual(events[0].platform, Platform.YOUTUBE)
        self.assertEqual(events[0].text, "hello YouTube")
        self.assertEqual((token, interval), ("next", 1000))
        self.assertIn("liveChat/messages", transport.calls[0][1])

    def test_youtube_discovers_active_live_chat(self) -> None:
        transport = FakeTransport({"items": [{"snippet": {"liveChatId": "live-active"}}]})
        adapter = YouTubeLiveChatAdapter(BearerCredentials("token"), transport)
        self.assertEqual(adapter.find_active_live_chat(), "live-active")
        self.assertIn("liveBroadcasts", transport.calls[0][1])

    def test_twitch_eventsub_normalizes_chat_notification(self) -> None:
        payload = {"metadata": {"message_type": "notification", "message_id": "evt-1", "message_timestamp": "2026-07-30T00:00:00Z"}, "payload": {"subscription": {"type": "channel.chat.message"}, "event": {"message_id": "chat-1", "broadcaster_user_id": "broadcaster-1", "broadcaster_user_login": "kur", "chatter_user_id": "viewer-1", "chatter_user_name": "Viewer", "message": {"text": "hello Twitch"}}}}
        event = TwitchEventSubAdapter.normalize_event(payload)
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.platform, Platform.TWITCH)
        self.assertEqual(event.text, "hello Twitch")

    def test_twitch_subscription_uses_authenticated_user_identity(self) -> None:
        transport = FakeTransport({"data": [{"id": "subscription-1"}]})
        adapter = TwitchEventSubAdapter(BearerCredentials("token", "client-1", "bot-user-1"), transport)
        self.assertEqual(adapter.create_chat_subscription("broadcaster-1", "session-1"), "subscription-1")
        body = json.loads(transport.calls[0][3])
        self.assertEqual(body["condition"]["user_id"], "bot-user-1")
        self.assertEqual(body["transport"]["session_id"], "session-1")

    def test_twitch_session_subscribes_after_welcome_and_ingests_notification(self) -> None:
        transport = FakeTransport({"data": [{"id": "subscription-1"}]})
        adapter = TwitchEventSubAdapter(BearerCredentials("token", "client-1", "bot-user-1"), transport)
        hub = PlatformEventHub()
        session = TwitchEventSubSession(adapter, hub, "broadcaster-1")
        session.handle_message({"metadata": {"message_type": "session_welcome"}, "payload": {"session": {"id": "session-1"}}})
        self.assertEqual(session.subscription_id, "subscription-1")
        notification = {"metadata": {"message_type": "notification", "message_id": "evt-1"}, "payload": {"subscription": {"type": "channel.chat.message"}, "event": {"message_id": "chat-1", "broadcaster_user_id": "broadcaster-1", "chatter_user_id": "viewer-1", "chatter_user_name": "Viewer", "message": {"text": "hello"}}}}
        self.assertEqual(len(session.handle_message(notification)), 1)

    def test_twitch_runner_dispatches_events_and_follows_reconnect(self) -> None:
        class Socket:
            def __init__(self):
                self.frames = [json.dumps({"metadata": {"message_type": "session_reconnect"}, "payload": {"session": {"reconnect_url": "wss://next"}}})]
                self.closed = False
            def recv(self): return self.frames.pop(0)
            def close(self): self.closed = True
        class Factory:
            def __init__(self): self.urls = []
            def connect(self, url): self.urls.append(url); return Socket()
        adapter = TwitchEventSubAdapter(BearerCredentials("token", "client-1", "bot-user-1"), FakeTransport({"data": [{"id": "sub"}]}))
        session = TwitchEventSubSession(adapter, PlatformEventHub(), "broadcaster-1")
        factory = Factory()
        runner = TwitchEventSubRunner(session, factory, lambda _events: None)
        self.assertEqual(runner.run_once(), "wss://next")
        self.assertEqual(factory.urls, ["wss://eventsub.wss.twitch.tv/ws"])

    def test_youtube_poller_discovers_and_advances_page(self) -> None:
        class PollAdapter:
            def find_active_live_chat(self): return "live-1"
            def list_messages(self, live_chat_id, page_token):
                return (PlatformEvent(Platform.YOUTUBE, "chat_message", "yt-1", live_chat_id, "user", "Viewer", "hello", "now"),), "next", 100
        poller = YouTubeLiveChatPoller(PollAdapter(), PlatformEventHub())
        self.assertEqual(len(poller.poll_once()), 1)
        self.assertEqual((poller.live_chat_id, poller.next_page_token, poller.polling_interval_ms), ("live-1", "next", 250))

    def test_twitch_eventsub_signature_rejects_stale_or_tampered_payload(self) -> None:
        secret = "a-secret-with-10-chars"
        message_id = "message-1"
        timestamp = "2026-07-30T00:00:00Z"
        body = b'{"payload":{}}'
        signature = "sha256=" + hmac.new(secret.encode(), message_id.encode() + timestamp.encode() + body, hashlib.sha256).hexdigest()
        now = 1785369600.0
        self.assertTrue(verify_twitch_eventsub_signature(message_id, timestamp, body, signature, secret, now=now, max_age_seconds=600))
        self.assertFalse(verify_twitch_eventsub_signature(message_id, timestamp, b"tampered", signature, secret, now=now, max_age_seconds=600))
        self.assertFalse(verify_twitch_eventsub_signature(message_id, timestamp, body, signature, secret, now=now + 601, max_age_seconds=600))

    def test_oauth_state_is_one_time(self) -> None:
        store = OAuthStateStore()
        state = store.issue()
        self.assertTrue(store.consume(state))
        self.assertFalse(store.consume(state))

    def test_oauth_client_uses_state_and_supports_refresh_and_revoke(self) -> None:
        transport = FakeOAuthTransport({"access_token": "access", "refresh_token": "refresh", "token_type": "Bearer", "expires_in": 3600, "scope": "chat:read"})
        provider = OAuthProvider("twitch", "https://id.twitch.tv/oauth2/authorize", "https://id.twitch.tv/oauth2/token", "client", "secret", ("chat:read",), "https://id.twitch.tv/oauth2/revoke")
        client = OAuthClient(provider, transport)
        url = client.authorization_url("http://127.0.0.1:8765/oauth/twitch/callback", "state-1")
        self.assertIn("state=state-1", url)
        token = client.exchange_code("code", "http://127.0.0.1:8765/oauth/twitch/callback")
        self.assertEqual(token.access_token, "access")
        self.assertEqual(client.refresh("refresh").refresh_token, "refresh")
        client.revoke("access")
        self.assertEqual(len(transport.calls), 3)

    def test_oauth_flow_manager_binds_provider_redirect_and_state(self) -> None:
        transport = FakeOAuthTransport({"access_token": "access", "token_type": "Bearer"})
        provider = OAuthProvider("youtube", "https://accounts.google.com/o/oauth2/v2/auth", "https://oauth2.googleapis.com/token", "client", "secret", ("scope",))
        manager = OAuthFlowManager({"youtube": OAuthClient(provider, transport)})
        url = manager.begin("youtube", "http://127.0.0.1:8765/callback")
        from urllib.parse import parse_qs, urlparse
        state = parse_qs(urlparse(url).query)["state"][0]
        token = manager.complete("youtube", "code", state, "http://127.0.0.1:8765/callback")
        self.assertEqual(token.access_token, "access")
        with self.assertRaisesRegex(ValueError, "invalid or expired"):
            manager.complete("youtube", "code", state, "http://127.0.0.1:8765/callback")

    def test_encrypted_token_store_round_trips_without_plaintext_file_content(self) -> None:
        from cryptography.fernet import Fernet
        with TemporaryDirectory() as directory:
            path = Path(directory) / "oauth_tokens.enc"
            store = EncryptedFileTokenStore(path, Fernet.generate_key())
            store.save("twitch", OAuthToken("access-secret", "Bearer", 3600, "refresh-secret", ("chat:read",), 100.0))
            self.assertNotIn(b"access-secret", path.read_bytes())
            self.assertEqual(store.load("twitch").refresh_token, "refresh-secret")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            store.delete("twitch")
            self.assertIsNone(store.load("twitch"))

    def test_outbound_action_requires_approval_and_is_audited(self) -> None:
        service = OutboundActionService()
        action = service.propose(OutboundAction(Platform.TWITCH, "chat_message", "broadcaster-1", "reply"))

        class Sender:
            def send_message(self, target_id, text):
                return "receipt-1"

        with self.assertRaisesRegex(ValueError, "requires operator approval"):
            service.send(action.action_id, Sender())
        approved = service.approve(action.action_id, "edited reply")
        self.assertEqual(approved.status, ActionStatus.APPROVED)
        sent, receipt = service.send(action.action_id, Sender())
        self.assertEqual((sent.status, receipt), (ActionStatus.SENT, "receipt-1"))
        self.assertEqual([item["event"] for item in service.audit()], ["proposed", "approved", "sent"])

    def test_outbound_action_and_audit_survive_restart(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "platform_actions.sqlite3"
            first = OutboundActionService(path)
            action = first.propose(OutboundAction(Platform.YOUTUBE, "chat_message", "live-chat-1", "reply", ("evt-1",)))
            first.approve(action.action_id, "edited reply")
            first.close()
            reopened = OutboundActionService(path)
            restored = reopened.get(action.action_id)
            self.assertIsNotNone(restored)
            assert restored is not None
            self.assertEqual((restored.status, restored.text), (ActionStatus.APPROVED, "edited reply"))
            self.assertEqual([item["event"] for item in reopened.audit()], ["proposed", "approved"])
            reopened.close()


if __name__ == "__main__":
    unittest.main()
