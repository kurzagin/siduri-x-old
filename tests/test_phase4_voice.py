from __future__ import annotations

import unittest

from packages.voice.queue import SpeechQueue
from packages.voice.voicevox import SpeechService, VoicevoxProvider, extract_amplitude_events


class FakeTransport:
    def __init__(self, speakers: list[dict[str, object]] | None = None) -> None:
        self.speakers = speakers if speakers is not None else [{"name": "ナースロボ＿タイプＴ", "speaker_uuid": "uuid-t", "styles": [{"id": 42, "name": "ノーマル"}]}]
        self.calls: list[tuple[str, dict[str, str]]] = []

    def get_json(self, path: str, query: dict[str, str] | None = None) -> object:
        self.calls.append((path, query or {}))
        return {"version": "fake"} if path == "/version" else self.speakers

    def post_json(self, path: str, query: dict[str, str], body: object | None = None) -> object:
        self.calls.append((path, query))
        return {"accent_phrases": []}

    def post_bytes(self, path: str, query: dict[str, str], body: object) -> bytes:
        self.calls.append((path, query))
        return b"RIFF-fake-wav"


class Phase4VoiceTests(unittest.TestCase):
    def test_discovers_speaker_by_metadata_and_synthesizes_without_fixed_id(self) -> None:
        transport = FakeTransport()
        provider = VoicevoxProvider(transport)
        speaker = provider.discover_speaker()
        audio = provider.synthesize("確認します。", speaker)
        self.assertEqual(speaker.speaker_id, "uuid-t")
        self.assertEqual(speaker.style_id, 42)
        self.assertEqual(audio.audio, b"RIFF-fake-wav")
        self.assertEqual(transport.calls[-1][1]["speaker"], "42")

    def test_missing_speaker_falls_back_to_subtitles(self) -> None:
        provider = VoicevoxProvider(FakeTransport([]))
        fallback: list[bool] = []
        result = SpeechService(provider).speak("発話", lambda: fallback.append(True))
        self.assertEqual(result.status, "subtitle_only")
        self.assertEqual(fallback, [True])

    def test_queue_orders_priority_and_supports_cancellation(self) -> None:
        queue = SpeechQueue()
        seen: list[str] = []
        queue.enqueue("low", 10, lambda: seen.append("low"))
        queue.enqueue("cancelled", 100, lambda: seen.append("cancelled"))
        queue.enqueue("high", 90, lambda: seen.append("high"))
        queue.cancel("cancelled")
        queue.run_next()
        queue.run_next()
        self.assertEqual(seen, ["high", "low"])

    def test_invalid_audio_is_safe_for_amplitude_visualizer(self) -> None:
        self.assertEqual(extract_amplitude_events(b"not-a-wav"), [])


if __name__ == "__main__":
    unittest.main()
