from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import socket
import threading
from dataclasses import replace
from pathlib import Path
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from uuid import uuid4

from .contracts import EventEnvelope, MockProvider
from packages.config.env import load_dotenv
from packages.config.providers import ProviderConfig, configured_provider_state
from packages.memory.service import MemoryItem, MemoryProposal, MemoryService
from packages.model_router.router import GenerationRequest, MockStructuredProvider, ModelRouter
from packages.model_router.registry import ProviderRegistry
from packages.model_router.telemetry import TelemetryRecorder
from packages.model_router.zai import ZaiProviderError, ZaiStructuredProvider
from packages.knowledge.eteyvat import EteyvatKnowledgeSource, EteyvatError
from packages.persona.domain import MeProfile, Recipient
from packages.persona.prompt import PromptAssembler, PromptContext
from packages.voice.queue import SpeechQueue
from packages.voice.voicevox import AmplitudeEvent, NullAudioSink, SpeechService, SystemAudioSink, UrllibVoicevoxTransport, VoicevoxProvider
from packages.observation.pipeline import FixtureObservationProvider, ObservationPipeline
from packages.observation.png import PixelRect, redact_png
from packages.observation.service import ObservationService
from packages.obs.capture import ObsCaptureBoundary, ObsWebSocketTransport
from packages.vision.contract import VisionObservationAdapter
from packages.vision.zai_glm5v import ZaiGlm5VisionProvider, ZaiGlm5VisionTransport

LOG = logging.getLogger("siduri.orchestrator")
CLIENTS: set[socket.socket] = set()
CLIENTS_LOCK = threading.Lock()
PROVIDER = MockProvider()
REPO_ROOT = Path(__file__).resolve().parents[4]
load_dotenv(REPO_ROOT / ".env")
VERSION = os.getenv("SIDURI_VERSION", "0.1.0-foundation")
DATA_ROOT = Path(os.getenv("SIDURI_DATA_DIR", str(REPO_ROOT / "data")))
ME_PATH = DATA_ROOT / "me.json"
ME_PROFILE = MeProfile.from_json_file(ME_PATH) if ME_PATH.exists() else MeProfile.from_json_file(REPO_ROOT / "config" / "me.example.json")
MEMORY = MemoryService(DATA_ROOT / "memory.sqlite3")
TELEMETRY = TelemetryRecorder(path=DATA_ROOT / "telemetry.jsonl")
ETEYVAT = EteyvatKnowledgeSource(os.getenv("SIDURI_ETEYVAT_URL", "https://eteyvat.krzgn.xyz"))
MODEL_PROVIDER = os.getenv("SIDURI_MODEL_PROVIDER", "zai" if os.getenv("ZAI_API_KEY") else "mock")
MODEL_NAME = os.getenv("SIDURI_MODEL_NAME", "glm-5.2")
MODEL_ENDPOINT = os.getenv("ZAI_API_BASE_URL", "https://api.z.ai/api/paas/v4")
MODEL_CONFIG = ProviderConfig(provider_id=MODEL_PROVIDER, model_id=MODEL_NAME,
    endpoint=MODEL_ENDPOINT if MODEL_PROVIDER == "zai" else None,
    capabilities=frozenset({"text_generation", "structured_generation"}),
    timeout_seconds=float(os.getenv("SIDURI_MODEL_TIMEOUT", "10")),
    token_budget=int(os.getenv("SIDURI_MODEL_TOKEN_BUDGET", "1200")),
    api_key_env="ZAI_API_KEY" if MODEL_PROVIDER == "zai" else None)
MODEL_CONFIG.validate()
VOICE_PROVIDER = VoicevoxProvider(UrllibVoicevoxTransport(os.getenv("SIDURI_VOICEVOX_URL", "http://127.0.0.1:50021")))
if MODEL_PROVIDER == "zai" and os.getenv("ZAI_API_KEY"):
    registry = ProviderRegistry((ZaiStructuredProvider(os.environ["ZAI_API_KEY"], model=MODEL_NAME, base_url=MODEL_ENDPOINT), MockStructuredProvider()))
    ROUTER = ModelRouter(registry.ordered(("zai-glm-5.2", "mock-structured")), telemetry=TELEMETRY)
else:
    registry = ProviderRegistry((MockStructuredProvider(),))
    ROUTER = ModelRouter(registry.ordered(("mock-structured",)), telemetry=TELEMETRY)
SPEECH_QUEUE = SpeechQueue()
VOICE_ENABLED = os.getenv("SIDURI_VOICEVOX_ENABLED", "true").lower() == "true"
OBSERVATIONS = ObservationPipeline(ttl_seconds=int(os.getenv("SIDURI_OBSERVATION_TTL_SECONDS", "30")))
FIXTURE_VISION = FixtureObservationProvider()
VISION_PROVIDER_MODE = os.getenv("SIDURI_VISION_PROVIDER", "fixture").lower()
if VISION_PROVIDER_MODE == "zai" and os.getenv("ZAI_API_KEY"):
    ACTIVE_VISION = VisionObservationAdapter(
        ZaiGlm5VisionProvider(
            ZaiGlm5VisionTransport(os.environ["ZAI_API_KEY"], MODEL_ENDPOINT),
            model=os.getenv("SIDURI_VISION_MODEL", "glm-5v-turbo"),
        ),
        instruction=os.getenv("SIDURI_VISION_INSTRUCTION", "Analyze only visible game evidence and return normalized observations."),
    )
else:
    ACTIVE_VISION = FIXTURE_VISION
OBS_SOURCE_NAME = os.getenv("SIDURI_OBS_SOURCE_NAME", "genshin")
OBS_TRANSPORT = ObsWebSocketTransport(os.getenv("SIDURI_OBS_URL", "ws://127.0.0.1:4455"), os.getenv("SIDURI_OBS_PASSWORD") or None)
OBS_CAPTURE = ObsCaptureBoundary(OBS_TRANSPORT, source_name=OBS_SOURCE_NAME,
                                 enabled=os.getenv("SIDURI_OBS_CAPTURE_ENABLED", "false").lower() == "true")


def configured_redactor() -> Any:
    raw = os.getenv("SIDURI_OBS_REDACTION_RECTS", "").strip()
    if not raw:
        return None
    rectangles: list[PixelRect] = []
    for item in raw.split(";"):
        parts = [int(value.strip()) for value in item.split(",")]
        if len(parts) != 4:
            raise ValueError("SIDURI_OBS_REDACTION_RECTS requires x,y,width,height entries")
        x, y, width, height = parts
        rectangles.append(PixelRect(x, y, x + width, y + height))
    return lambda frame: redact_png(frame, tuple(rectangles))


OBSERVATION_SERVICE = ObservationService(OBS_CAPTURE, OBSERVATIONS, ACTIVE_VISION, configured_redactor())


def voice_amplitude(event: AmplitudeEvent) -> None:
    envelope = EventEnvelope("SpeechAmplitude", {"offset_ms": event.offset_ms, "amplitude": event.amplitude}, source="voice", privacy_class="stream_safe")
    broadcast({"type": "speech_event", "event": envelope.to_dict()})


if os.getenv("SIDURI_AUDIO_ENABLED", "false").lower() == "true":
    try:
        AUDIO_SINK = SystemAudioSink()
    except Exception as error:
        LOG.warning("local audio playback unavailable; using silent sink: %s", type(error).__name__)
        AUDIO_SINK = NullAudioSink()
else:
    AUDIO_SINK = NullAudioSink()
VOICE_SERVICE = SpeechService(VOICE_PROVIDER, sink=AUDIO_SINK, on_amplitude=voice_amplitude)


def memory_dict(item: MemoryItem | MemoryProposal) -> dict[str, Any]:
    value = dict(item.__dict__)
    value["allowed_audiences"] = sorted(item.allowed_audiences)
    return value


def ws_frame(data: str) -> bytes:
    encoded = data.encode("utf-8")
    length = len(encoded)
    if length < 126:
        return bytes([0x81, length]) + encoded
    if length < 65536:
        return bytes([0x81, 126]) + length.to_bytes(2, "big") + encoded
    return bytes([0x81, 127]) + length.to_bytes(8, "big") + encoded


def broadcast(message: dict[str, Any]) -> None:
    frame = ws_frame(json.dumps(message, ensure_ascii=False))
    dead: list[socket.socket] = []
    with CLIENTS_LOCK:
        for client in CLIENTS:
            try:
                client.sendall(frame)
            except OSError:
                dead.append(client)
        for client in dead:
            CLIENTS.discard(client)


def queue_voice(plan: Any) -> None:
    if not VOICE_ENABLED:
        return
    job_id = f"speech_{plan.intent}_{id(plan)}"

    def speak() -> None:
        started = EventEnvelope("SpeechStarted", {"job_id": job_id}, source="voice", privacy_class="stream_safe")
        broadcast({"type": "speech_event", "event": started.to_dict()})
        result = VOICE_SERVICE.speak(plan.spoken_ja, lambda: broadcast({"type": "speech_event", "event": EventEnvelope("SubtitleFallback", {"job_id": job_id, "reason": "voice_unavailable"}, source="voice", privacy_class="stream_safe").to_dict()}))
        completed = EventEnvelope("SpeechCompleted", {"job_id": job_id, "status": result.status, "latency_ms": result.audio.latency_ms if result.audio else None, "reason": result.reason}, source="voice", privacy_class="stream_safe")
        broadcast({"type": "speech_event", "event": completed.to_dict()})
        TELEMETRY.record("speech_completed", status=result.status, latency_ms=round(result.audio.latency_ms, 2) if result.audio else None)

    SPEECH_QUEUE.enqueue(job_id, plan.speech_priority, speak, plan.interruptible)
    threading.Thread(target=SPEECH_QUEUE.run_next, name="siduri-speech", daemon=True).start()


class Handler(BaseHTTPRequestHandler):
    server_version = "SiduriFoundation/0.1"

    def log_message(self, fmt: str, *args: object) -> None:
        LOG.info("%s - %s", self.address_string(), fmt % args)

    def _json(self, status: int, body: dict[str, Any]) -> None:
        raw = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        value = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(value, dict):
            raise ValueError("request body must be a JSON object")
        return value

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._json(200, {"status": "ok"})
        elif self.path == "/ready":
            self._json(200, {"status": "ready", "dependencies": {"model_provider": configured_provider_state(MODEL_CONFIG, bool(os.getenv("ZAI_API_KEY")) if MODEL_PROVIDER == "zai" else True), "eteyvat": {"provider_id": ETEYVAT.source_id, "configured": True}, "voice": {"provider_id": VOICE_PROVIDER.provider_id, "enabled": VOICE_ENABLED}}})
        elif self.path == "/version":
            self._json(200, {"name": "siduri-orchestrator", "version": VERSION})
        elif self.path == "/voice/health":
            self._json(200, {"provider": VOICE_PROVIDER.provider_id, "configured": VOICE_ENABLED,
                             "healthy": VOICE_PROVIDER.health() if VOICE_ENABLED else False})
        elif self.path == "/obs/health":
            configured = bool(os.getenv("SIDURI_OBS_PASSWORD"))
            if not configured:
                self._json(200, {"configured": False, "source_name": OBS_SOURCE_NAME,
                                 "capture_enabled": OBS_CAPTURE.enabled, "reason": "password_not_configured"})
            else:
                try:
                    status = OBS_CAPTURE.status()
                    self._json(200, {"configured": True, "connected": status.connected, "streaming": status.streaming,
                                     "recording": status.recording, "source_name": OBS_SOURCE_NAME,
                                     "capture_enabled": status.capture_enabled})
                except (OSError, RuntimeError, ValueError):
                    self._json(503, {"configured": True, "connected": False, "source_name": OBS_SOURCE_NAME,
                                     "capture_enabled": OBS_CAPTURE.enabled, "reason": "obs_unavailable"})
        elif self.path == "/telemetry":
            self._json(200, {"events": TELEMETRY.events[-200:]})
        elif self.path == "/me":
            self._json(200, ME_PROFILE.to_dict())
        elif self.path == "/memory":
            self._json(200, {"items": [memory_dict(item) for item in MEMORY.list()]})
        elif self.path == "/memory/proposals":
            self._json(200, {"proposals": [memory_dict(proposal) for proposal in MEMORY.proposals()]})
        elif self.path == "/memory/audit":
            self._json(200, {"events": list(MEMORY.audit_events())})
        elif self.path == "/observations":
            OBSERVATIONS.expire()
            self._json(200, {"observations": [item.to_dict() for item in OBSERVATIONS.observations]})
        elif self.path == "/evidence":
            correlation_id = f"corr_{uuid4().hex}"
            try:
                results = ETEYVAT.search("Genshin Impact", limit=3)
                self._json(200, {"correlation_id": correlation_id, "source": ETEYVAT.source_id,
                                 "results": [{"title": item.title, "url": item.url, "revision": item.revision,
                                               "preview": item.preview, "endpoint": ETEYVAT.base_url} for item in results]})
            except EteyvatError:
                self._json(503, {"correlation_id": correlation_id, "source": ETEYVAT.source_id,
                                 "results": [], "error": "evidence_unavailable"})
        elif self.path == "/ws":
            self._websocket()
        else:
            self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        try:
            if self.path == "/dev/mock-response":
                knowledge = ()
                if os.getenv("SIDURI_ETEYVAT_ENABLED", "true").lower() == "true":
                    try:
                        knowledge = tuple((item.title, item.content[:1200], item.url, item.revision) for item in ETEYVAT.search("Genshin Impact", limit=3))
                    except EteyvatError:
                        TELEMETRY.record("knowledge_failure", provider_id=ETEYVAT.source_id)
                prompt = PromptAssembler(ME_PROFILE).assemble(PromptContext(recipient=Recipient.MASTER_STREAM, user_text="foundation mock request", memories=MEMORY.retrieve("foundation mock", Recipient.MASTER_STREAM), knowledge=knowledge))
                plan = ROUTER.generate(GenerationRequest(task="system_commentary", prompt=prompt, recipient="master_stream"))
                event = EventEnvelope(event_type="ResponsePlanCreated", payload=plan.to_dict())
                broadcast({"type": "response_plan", "event": event.to_dict()})
                queue_voice(plan)
                self._json(202, {"accepted": True, "event": event.to_dict()})
            elif self.path == "/dev/mock-observation":
                result = OBSERVATIONS.ingest(b"synthetic-genshin-frame-v1", source_name="fixture-genshin", provider=FIXTURE_VISION)
                if result.observation is None:
                    self._json(409, {"accepted": False, "reason": result.reason})
                    return
                event = EventEnvelope("ObservationCreated", result.observation.to_dict(), source="observation", privacy_class="private")
                broadcast({"type": "observation", "event": event.to_dict()})
                self._json(202, {"accepted": True, "event": event.to_dict()})
            elif self.path == "/dev/observe-now":
                result = OBSERVATION_SERVICE.observe_now()
                if result.observation is None:
                    self._json(409, {"accepted": False, "reason": result.capture_reason, "duplicate": result.duplicate})
                    return
                event = EventEnvelope("ObservationCreated", result.observation.to_dict(), source="observation", privacy_class="private")
                broadcast({"type": "observation", "event": event.to_dict()})
                self._json(202, {"accepted": True, "event": event.to_dict(), "duplicate": result.duplicate})
            elif self.path == "/dev/mock-observe-response":
                result = OBSERVATIONS.ingest(f"synthetic-observe-{uuid4().hex}".encode(), source_name="fixture-genshin", provider=FIXTURE_VISION)
                if result.observation is None:
                    self._json(409, {"accepted": False, "reason": result.reason})
                    return
                observation_event = EventEnvelope("ObservationCreated", result.observation.to_dict(), source="observation", privacy_class="private")
                broadcast({"type": "observation", "event": observation_event.to_dict()})
                prompt = PromptAssembler(ME_PROFILE).assemble(PromptContext(
                    recipient=Recipient.MASTER_STREAM,
                    user_text="fixture observation response request",
                    memories=MEMORY.retrieve("observation", Recipient.MASTER_STREAM),
                    observations=(result.observation,),
                ))
                plan = ROUTER.generate(GenerationRequest(task="observation_commentary", prompt=prompt, recipient="master_stream"))
                if result.observation.evidence_id not in plan.evidence_ids:
                    plan = replace(plan, evidence_ids=tuple(dict.fromkeys((*plan.evidence_ids, result.observation.evidence_id))),
                                   confidence=min(plan.confidence, result.observation.confidence))
                response_event = EventEnvelope("ResponsePlanCreated", plan.to_dict())
                broadcast({"type": "response_plan", "event": response_event.to_dict()})
                queue_voice(plan)
                self._json(202, {"accepted": True, "observation": observation_event.to_dict(), "response": response_event.to_dict()})
            elif self.path == "/memory":
                body = self._body()
                item = MEMORY.create(MemoryItem(content=str(body["content"]), provenance=str(body["provenance"]), sensitivity=str(body.get("sensitivity", "private")), allowed_audiences=frozenset(body.get("allowed_audiences", []))))
                self._json(201, {"item": memory_dict(item)})
            elif self.path == "/memory/proposals":
                body = self._body()
                proposal = MEMORY.propose(MemoryProposal(content=str(body["content"]), provenance=str(body["provenance"]), sensitivity=str(body.get("sensitivity", "private")), allowed_audiences=frozenset(body.get("allowed_audiences", []))))
                self._json(202, {"proposal": memory_dict(proposal)})
            elif self.path == "/memory/proposals/approve":
                proposal = MEMORY.approve(str(self._body()["proposal_id"]))
                self._json(200, {"item": memory_dict(proposal)})
            elif self.path == "/memory/proposals/reject":
                proposal = MEMORY.reject(str(self._body()["proposal_id"]))
                self._json(200, {"proposal": memory_dict(proposal)})
            else:
                self._json(404, {"error": "not_found"})
        except (KeyError, TypeError, ValueError) as error:
            self._json(400, {"error": str(error)})

    def do_PUT(self) -> None:  # noqa: N802
        global ME_PROFILE
        if self.path != "/me":
            self._json(404, {"error": "not_found"})
            return
        try:
            ME_PROFILE = MeProfile.from_dict(self._body())
            ME_PATH.parent.mkdir(parents=True, exist_ok=True)
            ME_PATH.write_text(json.dumps(ME_PROFILE.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self._json(200, ME_PROFILE.to_dict())
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            self._json(400, {"error": str(error)})

    def _websocket(self) -> None:
        if self.headers.get("Upgrade", "").lower() != "websocket":
            self._json(400, {"error": "websocket_upgrade_required"})
            return
        key = self.headers.get("Sec-WebSocket-Key", "")
        accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        self.send_response(HTTPStatus.SWITCHING_PROTOCOLS)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        client = self.connection
        with CLIENTS_LOCK:
            CLIENTS.add(client)
        LOG.info("WebSocket client connected")
        try:
            while client.recv(2):
                pass
        except (OSError, ConnectionError):
            pass
        finally:
            with CLIENTS_LOCK:
                CLIENTS.discard(client)
            LOG.info("WebSocket client disconnected")


def main() -> None:
    logging.basicConfig(level=os.getenv("SIDURI_LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    host = os.getenv("SIDURI_HOST", "127.0.0.1")
    port = int(os.getenv("SIDURI_PORT", "8765"))
    server = ThreadingHTTPServer((host, port), Handler)
    LOG.info("Siduri orchestrator listening on http://%s:%d", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOG.info("shutting down")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
