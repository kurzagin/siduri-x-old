from __future__ import annotations

import json
import io
import shutil
import struct
import subprocess
import threading
import urllib.error
import urllib.parse
import urllib.request
import wave
from dataclasses import dataclass
from time import monotonic
from typing import Any, Callable, Protocol


class VoicevoxError(RuntimeError):
    pass


@dataclass(frozen=True)
class SpeakerStyle:
    speaker_id: str
    speaker_name: str
    style_id: int
    style_name: str


@dataclass(frozen=True)
class SynthesizedAudio:
    audio: bytes
    speaker: SpeakerStyle
    latency_ms: float


@dataclass(frozen=True)
class AmplitudeEvent:
    offset_ms: int
    amplitude: float


def extract_amplitude_events(audio: bytes, window_ms: int = 50) -> list[AmplitudeEvent]:
    """Extract bounded visualizer events from PCM WAV without persisting audio."""
    if window_ms <= 0:
        raise ValueError("window_ms must be positive")
    try:
        with wave.open(io.BytesIO(audio), "rb") as stream:
            width, channels, rate = stream.getsampwidth(), stream.getnchannels(), stream.getframerate()
            if width not in {1, 2, 4} or channels <= 0 or rate <= 0:
                return []
            frames_per_window = max(1, rate * window_ms // 1000)
            events: list[AmplitudeEvent] = []
            offset = 0
            while raw := stream.readframes(frames_per_window):
                values = struct.unpack("<" + {1: "b", 2: "h", 4: "i"}[width] * (len(raw) // width), raw)
                peak = max(abs(value) for value in values) if values else 0
                scale = float(2 ** (width * 8 - 1))
                events.append(AmplitudeEvent(offset, min(1.0, peak / scale)))
                offset += window_ms
            return events
    except (wave.Error, EOFError, struct.error):
        return []


class VoicevoxTransport(Protocol):
    def get_json(self, path: str, query: dict[str, str] | None = None) -> object: ...
    def post_json(self, path: str, query: dict[str, str], body: object | None = None) -> object: ...
    def post_bytes(self, path: str, query: dict[str, str], body: object) -> bytes: ...


class UrllibVoicevoxTransport:
    def __init__(self, base_url: str = "http://127.0.0.1:50021", timeout_seconds: float = 5.0,
                 opener: Callable[..., Any] = urllib.request.urlopen) -> None:
        parsed = urllib.parse.urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("VOICEVOX endpoint must be an absolute HTTP(S) URL")
        if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise ValueError("non-local VOICEVOX endpoints must use HTTPS")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._opener = opener

    def _request(self, method: str, path: str, query: dict[str, str] | None = None, body: bytes | None = None,
                 accept: str = "application/json") -> bytes:
        url = self.base_url + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        request = urllib.request.Request(url, data=body, headers={"Accept": accept, "Content-Type": "application/json"}, method=method)
        try:
            with self._opener(request, timeout=self.timeout_seconds) as response:
                return response.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as error:
            raise VoicevoxError("VOICEVOX request failed") from error

    def get_json(self, path: str, query: dict[str, str] | None = None) -> object:
        try:
            return json.loads(self._request("GET", path, query).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise VoicevoxError("VOICEVOX returned invalid JSON") from error

    def post_json(self, path: str, query: dict[str, str], body: object | None = None) -> object:
        raw = json.dumps(body if body is not None else {}).encode("utf-8")
        try:
            return json.loads(self._request("POST", path, query, raw).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise VoicevoxError("VOICEVOX returned invalid JSON") from error

    def post_bytes(self, path: str, query: dict[str, str], body: object) -> bytes:
        return self._request("POST", path, query, json.dumps(body).encode("utf-8"), "audio/wav")


class VoicevoxProvider:
    provider_id = "voicevox"
    capabilities = frozenset({"text_to_speech"})

    def __init__(self, transport: VoicevoxTransport, speaker_aliases: tuple[str, ...] = (
        "ナースロボ＿タイプＴ", "ナースロボ_タイプT", "Nurse Robo Type T")) -> None:
        self.transport = transport
        self.speaker_aliases = tuple(self._normalize(alias) for alias in speaker_aliases)
        self._speaker: SpeakerStyle | None = None

    def health(self) -> bool:
        try:
            self.transport.get_json("/version")
            return True
        except VoicevoxError:
            return False

    def discover_speaker(self, style_name: str = "ノーマル") -> SpeakerStyle:
        value = self.transport.get_json("/speakers")
        if not isinstance(value, list):
            raise VoicevoxError("VOICEVOX speakers response was not a list")
        for speaker in value:
            if not isinstance(speaker, dict) or not isinstance(speaker.get("name"), str):
                continue
            if self._normalize(speaker["name"]) not in self.speaker_aliases:
                continue
            styles = speaker.get("styles", [])
            if not isinstance(styles, list):
                continue
            selected = next((style for style in styles if isinstance(style, dict) and style.get("name") == style_name), None)
            selected = selected or next((style for style in styles if isinstance(style, dict)), None)
            if isinstance(selected, dict) and isinstance(selected.get("id"), int) and isinstance(speaker.get("speaker_uuid"), str):
                result = SpeakerStyle(speaker["speaker_uuid"], speaker["name"], selected["id"], str(selected.get("name", "")))
                self._speaker = result
                return result
        raise VoicevoxError("Nurse Robo Type T speaker/style was not found")

    def synthesize(self, text: str, speaker: SpeakerStyle | None = None) -> SynthesizedAudio:
        if not text.strip() or len(text) > 2000:
            raise ValueError("speech text must be non-empty and bounded")
        selected = speaker or self._speaker or self.discover_speaker()
        started = monotonic()
        query = self.transport.post_json("/audio_query", {"text": text, "speaker": str(selected.style_id)})
        if not isinstance(query, dict):
            raise VoicevoxError("VOICEVOX audio query was not an object")
        audio = self.transport.post_bytes("/synthesis", {"speaker": str(selected.style_id)}, query)
        if not audio:
            raise VoicevoxError("VOICEVOX returned empty audio")
        return SynthesizedAudio(audio, selected, (monotonic() - started) * 1000)

    @staticmethod
    def _normalize(value: str) -> str:
        return "".join(value.casefold().split()).replace("＿", "_")


class NullAudioSink:
    """Safe default sink: accepts audio but never plays it or touches public systems."""
    def play(self, audio: SynthesizedAudio) -> None:
        return None


class SystemAudioSink:
    """Play WAV bytes through an installed local audio command."""
    def __init__(self, command: str | None = None) -> None:
        self.command = command or next((candidate for candidate in ("ffplay", "pw-play", "paplay") if shutil.which(candidate)), None)
        if not self.command:
            raise VoicevoxError("no supported local audio playback command was found")

    def play(self, audio: SynthesizedAudio) -> None:
        if self.command == "ffplay":
            args = [self.command, "-nodisp", "-autoexit", "-loglevel", "error", "-i", "-"]
        else:
            args = [self.command, "-"]
        try:
            completed = subprocess.run(args, input=audio.audio, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False, timeout=120)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise VoicevoxError("local audio playback failed") from error
        if completed.returncode != 0:
            raise VoicevoxError("local audio playback returned an error")


@dataclass(frozen=True)
class SpeechResult:
    status: str
    audio: SynthesizedAudio | None = None
    reason: str | None = None


class SpeechService:
    def __init__(self, provider: VoicevoxProvider, sink: Any | None = None,
                 on_amplitude: Callable[[AmplitudeEvent], None] | None = None) -> None:
        self.provider = provider
        self.sink = sink or NullAudioSink()
        self.on_amplitude = on_amplitude
        self._lock = threading.Lock()
        self._cancelled = False

    def speak(self, spoken_ja: str, subtitle_fallback: Callable[[], None] | None = None) -> SpeechResult:
        with self._lock:
            self._cancelled = False
        try:
            audio = self.provider.synthesize(spoken_ja)
            with self._lock:
                if self._cancelled:
                    return SpeechResult("cancelled", audio, "cancelled before playback")
            if self.on_amplitude:
                for event in extract_amplitude_events(audio.audio):
                    self.on_amplitude(event)
            self.sink.play(audio)
            return SpeechResult("spoken", audio)
        except (VoicevoxError, ValueError) as error:
            if subtitle_fallback:
                subtitle_fallback()
            return SpeechResult("subtitle_only", reason=str(error))

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True
