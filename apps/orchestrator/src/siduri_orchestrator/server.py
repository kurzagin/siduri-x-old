from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import socket
import threading
from dataclasses import replace
from pathlib import Path
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from uuid import uuid4
from urllib.parse import parse_qs, urlparse

from .contracts import EventEnvelope, MockProvider, ResponsePlan
from packages.config.env import load_dotenv
from packages.config.providers import ProviderConfig, configured_provider_state
from packages.memory.service import MemoryItem, MemoryProposal, MemoryService, SourceEvent, BehavioralDirective, Scope, BehaviorDef
from packages.memory.postgres import SupabaseMemoryService
from packages.memory.teaching import extract_explicit_teaching
from packages.persona.behavior import ActiveSelfCompiler
from packages.model_router.router import GenerationRequest, MockStructuredProvider, ModelRouter, ProviderUnavailableError
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
from packages.observation.grounding import current_observations, resolve_visible_labels
from packages.obs.capture import ObsCaptureBoundary, ObsWebSocketTransport
from packages.vision.contract import VisionObservationAdapter
from packages.vision.multipass import MultiPassVisionProvider
from packages.vision.crops import CroppedVisionProvider, ImageRegion
from packages.vision.zai_glm5v import ZaiGlm5VisionProvider, ZaiGlm5VisionTransport
from packages.platforms.adapters import BearerCredentials, TwitchEventSubAdapter, YouTubeLiveChatAdapter
from packages.platforms.contracts import ActionStatus, OutboundAction, OutboundActionService, Platform, PlatformEvent, PlatformEventHub, PlatformIngressGuard, utc_now
from packages.platforms.auth import EncryptedFileTokenStore, OAuthClient, OAuthFlowManager, OAuthProvider
from packages.platforms.sessions import OptionalTwitchSocketFactory, TwitchEventSubRunner, TwitchEventSubSession, YouTubeLiveChatPoller, YouTubeLiveChatRunner

LOG = logging.getLogger("siduri.orchestrator")
ALLOWED_ORIGINS = {"http://localhost:3000", "http://127.0.0.1:3000"}
CLIENTS: set[socket.socket] = set()
CLIENTS_LOCK = threading.Lock()
PENDING_RESPONSES: dict[str, tuple[ResponsePlan, dict[str, Any]]] = {}
PROVIDER = MockProvider()
REPO_ROOT = Path(__file__).resolve().parents[4]
load_dotenv(REPO_ROOT / ".env")
VERSION = os.getenv("SIDURI_VERSION", "0.1.0-foundation")
DATA_ROOT = Path(os.getenv("SIDURI_DATA_DIR", str(REPO_ROOT / "data")))
ME_PATH = DATA_ROOT / "me.json"
ME_PROFILE = MeProfile.from_json_file(ME_PATH) if ME_PATH.exists() else MeProfile.from_json_file(REPO_ROOT / "config" / "me.example.json")
SUPABASE_DATABASE_URL = os.getenv("SIDURI_SUPABASE_DATABASE_URL", "").strip()
MEMORY_PERSISTENT = bool(SUPABASE_DATABASE_URL)
MEMORY = (
    SupabaseMemoryService.connect(SUPABASE_DATABASE_URL)
    if MEMORY_PERSISTENT
    else MemoryService()
)
TELEMETRY = TelemetryRecorder(path=DATA_ROOT / "telemetry.jsonl")
ETEYVAT = EteyvatKnowledgeSource(
    os.getenv("SIDURI_ETEYVAT_URL", "https://eteyvat.krzgn.xyz"),
    timeout_seconds=float(os.getenv("SIDURI_ETEYVAT_TIMEOUT", "3")),
)
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
    registry = ProviderRegistry((ZaiStructuredProvider(os.environ["ZAI_API_KEY"], model=MODEL_NAME, base_url=MODEL_ENDPOINT),))
    ROUTER = ModelRouter(registry.ordered(("zai-glm-5.2",)), telemetry=TELEMETRY)
else:
    registry = ProviderRegistry((MockStructuredProvider(),))
    ROUTER = ModelRouter(registry.ordered(("mock-structured",)), telemetry=TELEMETRY)
SPEECH_QUEUE = SpeechQueue()
VOICE_ENABLED = os.getenv("SIDURI_VOICEVOX_ENABLED", "true").lower() == "true"
OBSERVATIONS = ObservationPipeline(ttl_seconds=int(os.getenv("SIDURI_OBSERVATION_TTL_SECONDS", "30")))
FIXTURE_VISION = FixtureObservationProvider()
VISION_PROVIDER_MODE = os.getenv("SIDURI_VISION_PROVIDER", "fixture").lower()
DEFAULT_VISION_INSTRUCTION = (
    "Analyze only visible game evidence. Return JSON with a readings array; each reading must have "
    "entity, value, confidence, source_crop, ocr_text, and competing_interpretations. "
    "Never infer hidden state. If the frame is unclear or no label is readable, return exactly one "
    "scene reading with value 'no usable visible evidence', confidence 0.0, and explain the uncertainty."
)
if VISION_PROVIDER_MODE == "zai" and os.getenv("ZAI_API_KEY"):
    vision_transport = ZaiGlm5VisionTransport(
        os.environ["ZAI_API_KEY"], MODEL_ENDPOINT,
        timeout_seconds=float(os.getenv("SIDURI_VISION_TIMEOUT", "15")),
    )
    vision_model = os.getenv("SIDURI_VISION_MODEL", "glm-5v-turbo")
    vision_provider = ZaiGlm5VisionProvider(vision_transport, model=vision_model)
    context_pass = VisionObservationAdapter(vision_provider, os.getenv("SIDURI_VISION_INSTRUCTION", DEFAULT_VISION_INSTRUCTION))
    detail_pass = VisionObservationAdapter(vision_provider, os.getenv(
        "SIDURI_VISION_DETAIL_INSTRUCTION",
        "Inspect visible HUD text and named entities, especially quest text and party labels. "
        "Read every visible party member and identify the active member only when the active indicator is visible. "
        "Return only readable evidence with confidence and competing interpretations. Do not infer hidden state.",
    ))
    if os.getenv("SIDURI_VISION_CROP_ENABLED", "true").lower() == "true":
        detail_pass = CroppedVisionProvider(detail_pass, ImageRegion("right-party-hud", 1640, 180, 280, 460), top_party_is_active=True)
    if os.getenv("SIDURI_VISION_MULTIPASS", "true").lower() == "true":
        ACTIVE_VISION = MultiPassVisionProvider((context_pass, detail_pass), provider_id=vision_provider.provider_id, model_id=vision_provider.model_id)
    else:
        ACTIVE_VISION = context_pass
else:
    ACTIVE_VISION = FIXTURE_VISION
OBS_SOURCE_NAME = os.getenv("SIDURI_OBS_SOURCE_NAME", "genshin")
OBS_TRANSPORT = ObsWebSocketTransport(os.getenv("SIDURI_OBS_URL", "ws://127.0.0.1:4455"), os.getenv("SIDURI_OBS_PASSWORD") or None)
OBS_CAPTURE = ObsCaptureBoundary(OBS_TRANSPORT, source_name=OBS_SOURCE_NAME,
                                 enabled=os.getenv("SIDURI_OBS_CAPTURE_ENABLED", "false").lower() == "true")
PLATFORM_EVENTS = PlatformEventHub(guard=PlatformIngressGuard())
PLATFORM_ACTIONS = OutboundActionService(DATA_ROOT / "platform_actions.sqlite3")
PLATFORM_STOP = threading.Event()
PLATFORM_WORKERS: list[threading.Thread] = []
PLATFORM_SENDERS: dict[Platform, Any] = {}
OAUTH_TOKENS: dict[str, Any] = {}
oauth_clients: dict[str, OAuthClient] = {}
if os.getenv("SIDURI_YOUTUBE_CLIENT_ID") and os.getenv("SIDURI_YOUTUBE_CLIENT_SECRET"):
    oauth_clients["youtube"] = OAuthClient(OAuthProvider(
        "youtube", "https://accounts.google.com/o/oauth2/v2/auth", "https://oauth2.googleapis.com/token",
        os.environ["SIDURI_YOUTUBE_CLIENT_ID"], os.environ["SIDURI_YOUTUBE_CLIENT_SECRET"],
        tuple(filter(None, os.getenv("SIDURI_YOUTUBE_OAUTH_SCOPES", "https://www.googleapis.com/auth/youtube.readonly").split())),
        "https://oauth2.googleapis.com/revoke",
    ))
if os.getenv("SIDURI_TWITCH_CLIENT_ID") and os.getenv("SIDURI_TWITCH_CLIENT_SECRET"):
    oauth_clients["twitch"] = OAuthClient(OAuthProvider(
        "twitch", "https://id.twitch.tv/oauth2/authorize", "https://id.twitch.tv/oauth2/token",
        os.environ["SIDURI_TWITCH_CLIENT_ID"], os.environ["SIDURI_TWITCH_CLIENT_SECRET"],
        tuple(filter(None, os.getenv("SIDURI_TWITCH_OAUTH_SCOPES", "user:read:chat user:write:chat").split())),
        "https://id.twitch.tv/oauth2/revoke",
    ))
if os.getenv("SIDURI_OAUTH_ENCRYPTION_KEY"):
    OAUTH_TOKEN_STORE = EncryptedFileTokenStore(os.getenv("SIDURI_OAUTH_TOKEN_FILE", str(DATA_ROOT / "oauth_tokens.enc")), os.environ["SIDURI_OAUTH_ENCRYPTION_KEY"])
else:
    OAUTH_TOKEN_STORE = None
OAUTH_FLOWS = OAuthFlowManager(oauth_clients, token_store=OAUTH_TOKEN_STORE)
if os.getenv("SIDURI_YOUTUBE_ACCESS_TOKEN"):
    PLATFORM_SENDERS[Platform.YOUTUBE] = YouTubeLiveChatAdapter(
        BearerCredentials(os.environ["SIDURI_YOUTUBE_ACCESS_TOKEN"]),
    )
if os.getenv("SIDURI_TWITCH_ACCESS_TOKEN") and os.getenv("SIDURI_TWITCH_CLIENT_ID") and os.getenv("SIDURI_TWITCH_USER_ID"):
    PLATFORM_SENDERS[Platform.TWITCH] = TwitchEventSubAdapter(
        BearerCredentials(os.environ["SIDURI_TWITCH_ACCESS_TOKEN"], os.environ["SIDURI_TWITCH_CLIENT_ID"], os.getenv("SIDURI_TWITCH_USER_ID")),
    )


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


def platform_event_from_body(body: dict[str, Any]) -> PlatformEvent:
    try:
        platform = Platform(str(body["platform"]))
    except (KeyError, ValueError) as error:
        raise ValueError("platform must be youtube or twitch") from error
    return PlatformEvent(
        platform=platform,
        event_type=str(body.get("event_type", "chat_message")),
        source_message_id=str(body["source_message_id"]),
        channel_id=str(body["channel_id"]),
        author_id=str(body["author_id"]),
        author_display_name=str(body.get("author_display_name", "unknown")),
        text=str(body["text"]),
        occurred_at=str(body.get("occurred_at", utc_now())),
        metadata={str(key): str(value) for key, value in body.get("metadata", {}).items()} if isinstance(body.get("metadata", {}), dict) else {},
    )


def platform_reply_suggestion(event_id: str, language: str = "en") -> tuple[ResponsePlan, OutboundAction]:
    event = next((item for item in PLATFORM_EVENTS.events() if item.event_id == event_id), None)
    if event is None:
        raise KeyError(event_id)
    if language not in {"ja", "en", "id"}:
        raise ValueError("language must be ja, en, or id")
    assembler = PromptAssembler(ME_PROFILE)
    context = PromptContext(
        recipient=Recipient.VIEWER_DIRECT,
        user_text=f"[PLATFORM EVENT] platform={event.platform.value}; author={event.author_display_name}; message={event.text}",
        behavioral_directives=MEMORY.list_active_behavioral_directives(),
    )
    plan = ROUTER.generate(GenerationRequest(
        task="platform_reply_suggestion",
        prompt=assembler.context_prompt(context),
        system_prompt=assembler.system_prompt(context),
        recipient=Recipient.VIEWER_DIRECT.value,
    ))
    plan = replace(plan, recipient=Recipient.VIEWER_DIRECT.value, intent="platform_reply_suggestion", requires_operator_approval=True, evidence_ids=(event.event_id,))
    text = {"ja": plan.spoken_ja, "en": plan.subtitle_en, "id": plan.subtitle_id}[language]
    action = PLATFORM_ACTIONS.propose(OutboundAction(
        platform=event.platform, action_type="chat_message", target_id=event.channel_id, text=text, evidence_ids=(event.event_id,),
    ))
    return plan, action


def refresh_platform_sender(provider_id: str, token: Any) -> None:
    OAUTH_TOKENS[provider_id] = token
    if provider_id == "youtube":
        PLATFORM_SENDERS[Platform.YOUTUBE] = YouTubeLiveChatAdapter(BearerCredentials(token.access_token))
    elif provider_id == "twitch":
        PLATFORM_SENDERS[Platform.TWITCH] = TwitchEventSubAdapter(BearerCredentials(token.access_token, os.getenv("SIDURI_TWITCH_CLIENT_ID"), os.getenv("SIDURI_TWITCH_USER_ID")))


for _provider_id in oauth_clients:
    _stored_token = OAUTH_FLOWS.load(_provider_id)
    if _stored_token is not None and not _stored_token.expired():
        refresh_platform_sender(_provider_id, _stored_token)


def start_platform_workers() -> None:
    if os.getenv("SIDURI_PLATFORM_INGEST_ENABLED", "false").lower() != "true":
        return

    def on_events(events: tuple[PlatformEvent, ...]) -> None:
        for event in events:
            LOG.info("platform event accepted: platform=%s event_type=%s", event.platform.value, event.event_type)

    youtube_sender = PLATFORM_SENDERS.get(Platform.YOUTUBE)
    if isinstance(youtube_sender, YouTubeLiveChatAdapter):
        runner = YouTubeLiveChatRunner(YouTubeLiveChatPoller(youtube_sender, PLATFORM_EVENTS), on_events)
        worker = threading.Thread(target=runner.run_forever, args=(PLATFORM_STOP,), name="siduri-youtube-chat", daemon=True)
        worker.start()
        PLATFORM_WORKERS.append(worker)

    twitch_sender = PLATFORM_SENDERS.get(Platform.TWITCH)
    broadcaster_id = os.getenv("SIDURI_TWITCH_BROADCASTER_ID")
    if isinstance(twitch_sender, TwitchEventSubAdapter) and broadcaster_id:
        session = TwitchEventSubSession(twitch_sender, PLATFORM_EVENTS, broadcaster_id)
        runner = TwitchEventSubRunner(session, OptionalTwitchSocketFactory(), on_events)
        worker = threading.Thread(target=runner.run_forever, args=(PLATFORM_STOP,), name="siduri-twitch-eventsub", daemon=True)
        worker.start()
        PLATFORM_WORKERS.append(worker)


def stop_platform_workers() -> None:
    PLATFORM_STOP.set()
    for worker in PLATFORM_WORKERS:
        worker.join(timeout=2)


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


def grounded_response(observation: Any, correlation_id: str) -> tuple[ResponsePlan, dict[str, Any], str]:
    """Assemble and generate one response from one current observation."""
    grounding = resolve_visible_labels(observation, ETEYVAT)
    assembler = PromptAssembler(ME_PROFILE)
    context = PromptContext(
        recipient=Recipient.MASTER_STREAM,
        user_text="live observation response request",
        memories=MEMORY.retrieve_claims("observation", Recipient.MASTER_STREAM),
        observations=(observation,),
        knowledge=grounding.prompt_items,
        behavioral_directives=MEMORY.list_active_behavioral_directives(),
    )
    plan = ROUTER.generate(GenerationRequest(
        task="observation_commentary",
        prompt=assembler.context_prompt(context),
        system_prompt=assembler.system_prompt(context),
        recipient="master_stream",
    ))
    evidence_ids = [observation.evidence_id, *(item["evidence_id"] for item in grounding.citations)]
    plan = replace(plan, evidence_ids=tuple(dict.fromkeys(evidence_ids))[:32],
                   confidence=min(plan.confidence, observation.confidence),
                   requires_operator_approval=True)
    metadata = {"correlation_id": correlation_id, "citations": list(grounding.citations),
                "observation_evidence_id": observation.evidence_id,
                "knowledge_source": ETEYVAT.source_id, "knowledge_revision": ETEYVAT.revision,
                "knowledge_endpoint": ETEYVAT.base_url}
    return plan, metadata, assembler.assemble(context)


def stage_response(plan: ResponsePlan, metadata: dict[str, Any]) -> None:
    PENDING_RESPONSES[metadata["correlation_id"]] = (plan, metadata)


def approve_response(correlation_id: str) -> tuple[ResponsePlan, dict[str, Any]]:
    pending = PENDING_RESPONSES.pop(correlation_id, None)
    if pending is None:
        raise ValueError("response approval is missing or expired")
    plan, metadata = pending
    return replace(plan, requires_operator_approval=False), metadata


def private_chat_response(body: dict[str, Any]) -> tuple[ResponsePlan, dict[str, Any]]:
    message = body.get("message")
    if not isinstance(message, str) or not message.strip() or len(message) > 4000:
        raise ValueError("message must be a non-empty string of at most 4000 characters")
    teaching = extract_explicit_teaching(message)
    model_message = message
    raw_history = body.get("history", [])
    if not isinstance(raw_history, list) or len(raw_history) > 20:
        raise ValueError("history must be a bounded list")
    if any(
        not isinstance(item, dict)
        or item.get("role") not in {"user", "assistant"}
        or not isinstance(item.get("content"), str)
        for item in raw_history
    ):
        raise ValueError("history entries must contain role and content")

    history_lines: list[str] = []
    for item in raw_history:
        content = item["content"][:2000].replace("\x00", "")
        history_lines.append(f"- {item['role']}: {content}")
    observations = current_observations(OBSERVATIONS)
    knowledge: list[tuple[str, str, str, str | None]] = []
    citations: list[dict[str, object]] = []
    normalized_message = re.sub(r"\s+", " ", model_message.casefold()).strip()
    self_identity_request = bool(re.search(
        r"\b(?:who|what)\s+are\s+you\b|\bwho\s+is\s+siduri\b|\b(?:your|my)\s+name\b|\btell\s+me\s+about\s+yourself\b",
        normalized_message,
    ))
    external_knowledge_request = not self_identity_request and bool(re.search(
        r"\b(?:tell me about|who is|what is|explain|lore|build|materials?|farm(?:ing)?|where (?:is|are|can i find)|how (?:do|can) i)\b",
        normalized_message,
    ))
    should_query_eteyvat = external_knowledge_request and not (teaching.claims or teaching.runtime_effects)
    try:
        knowledge_results = ETEYVAT.search(model_message, limit=3) if should_query_eteyvat else []
        if not knowledge_results:
            subject = model_message
            extracted = re.search(r"(?:about|regarding|on|what is|who is)\s+(.+?)[?.!]*$", model_message, re.IGNORECASE)
            if extracted:
                subject = extracted.group(1).strip()
            knowledge_results = ETEYVAT.find_entity(subject[:200], limit=3) if should_query_eteyvat else []
        for item in knowledge_results:
            knowledge.append((item.title, item.content[:1600], item.url, item.revision))
            citations.append({"evidence_id": item.result_id, "title": item.title, "url": item.url,
                              "revision": item.revision, "preview": item.preview})
    except EteyvatError:
        TELEMETRY.record("knowledge_failure", provider_id=ETEYVAT.source_id, task="private_chat")
    query_text = " ".join([item["content"] for item in raw_history]) + " " + message
    active_behavioral = MEMORY.list_active_behavioral_directives()
    compiled_behavior = ActiveSelfCompiler().compile(active_behavioral, Recipient.MASTER_PRIVATE)
    TELEMETRY.record("behavioral_memory_compiled", active_count=len(compiled_behavior.active_ids), excluded_count=len(compiled_behavior.excluded_ids), audience=Recipient.MASTER_PRIVATE.value)

    assembler = PromptAssembler(ME_PROFILE)
    context = PromptContext(
        recipient=Recipient.MASTER_PRIVATE,
        user_text="[CHAT HISTORY]\n" + ("\n".join(history_lines) or "- none") + f"\n[CURRENT MESSAGE]\n{model_message}",
        memories=(*MEMORY.retrieve_claims(query_text, Recipient.MASTER_PRIVATE), *MEMORY.retrieve(query_text, Recipient.MASTER_PRIVATE)),
        observations=observations,
        knowledge=tuple(knowledge),
        behavioral_directives=active_behavioral,
        compiled_behavior=compiled_behavior,
    )
    plan = ROUTER.generate(GenerationRequest(
        task="private_chat",
        prompt=assembler.context_prompt(context),
        system_prompt=assembler.system_prompt(context),
        recipient=Recipient.MASTER_PRIVATE.value,
        timeout_seconds=MODEL_CONFIG.timeout_seconds,
    ))
    memory_candidates = list(teaching.claims)
    known_claims = {(item.get("subject"), item.get("predicate")) for item in memory_candidates}
    memory_candidates.extend(
        item for item in plan.memory_proposals
        if (item.get("subject"), item.get("predicate")) not in known_claims
        and "[LOCAL SECRET REDACTED]" not in str(item.get("content", ""))
        and "[LOCAL SECRET REDACTED]" not in str(item.get("value", ""))
    )
    behavioral_candidates = list(teaching.runtime_effects)

    def runtime_effect_key(item: dict[str, Any]) -> tuple[str, str, str]:
        subject = str(item.get("subject", "")).strip().casefold()
        if subject in {"master", "master_private", "user", "primary_user"}:
            subject = "primary_user"
        predicate = str(item.get("predicate", "")).strip().casefold()
        predicate = re.sub(r"_(?:private|public|stream)$", "", predicate)
        value = str(item.get("value", "")).strip().casefold()
        return subject, predicate, value

    known_effects = {runtime_effect_key(item) for item in behavioral_candidates}
    behavioral_candidates.extend(
        item for item in plan.behavioral_proposals
        if runtime_effect_key(item) not in known_effects
    )

    pending_proposals: list[dict[str, Any]] = []
    source_event: SourceEvent | None = None
    if memory_candidates or behavioral_candidates:
        source_event = MEMORY.add_source_event(SourceEvent(
            event_id=f"evt_{uuid4().hex}",
            source_type="private_chat",
            occurred_at=utc_now(),
            payload={"message": message},
        ))
    for candidate in memory_candidates:
        if any(
            claim.status == "confirmed"
            and claim.subject == candidate.get("subject", "primary_user")
            and claim.predicate == candidate.get("predicate", "note")
            and claim.value == candidate.get("value", candidate["content"])
            for claim in MEMORY.claims()
        ):
            continue
        proposal = MEMORY.propose(MemoryProposal(
            content=candidate["content"], provenance=candidate.get("provenance", "system_private_chat"),
            sensitivity=candidate.get("sensitivity", "private"),
            allowed_audiences=frozenset(candidate.get("allowed_audiences", [Recipient.MASTER_PRIVATE.value])),
            subject=candidate.get("subject", "primary_user"),
            predicate=candidate.get("predicate", "note"),
            value=candidate.get("value", candidate["content"]),
            claim_type=candidate.get("claim_type", "semantic"),
            source_event_id=source_event.event_id if source_event else None,
        ))
        pending_proposals.append(memory_dict(proposal))
    pending_behavioral: list[dict[str, Any]] = []
    for bp in behavioral_candidates:
        scope_dict = bp.get("scope", {})
        behavior_dict = bp.get("behavior", {})
        scope = Scope(tuple(scope_dict.get("recipient_ids", [])), tuple(scope_dict.get("audiences", [])), tuple(scope_dict.get("session_modes", [])))
        existing_directives = MEMORY.list_all_behavioral_directives()
        if any(
            existing.status in {"pending", "confirmed"}
            and existing.domain == bp.get("domain", "")
            and existing.subject == bp.get("subject", "")
            and existing.predicate == bp.get("predicate", "")
            and existing.value == bp.get("value", "")
            and existing.scope == scope
            and existing.behavior.instruction == behavior_dict.get("instruction", "")
            for existing in existing_directives
        ):
            continue
        new_audiences = set(scope.audiences)
        superseded = next((
            existing for existing in sorted(existing_directives, key=lambda item: item.created_at, reverse=True)
            if existing.status == "confirmed"
            and existing.domain == bp.get("domain", "")
            and existing.subject == bp.get("subject", "")
            and existing.predicate == bp.get("predicate", "")
            and (
                not existing.scope.audiences
                or not new_audiences
                or bool(set(existing.scope.audiences) & new_audiences)
            )
        ), None)
        directive = BehavioralDirective(
            directive_id=f"dir_{uuid4().hex}",
            memory_class=bp.get("memory_class", "behavioral"),
            domain=bp.get("domain", ""),
            subject=bp.get("subject", ""),
            predicate=bp.get("predicate", ""),
            value=bp.get("value", ""),
            activation=bp.get("activation", "always_when_scope_matches"),
            scope=scope,
            behavior=BehaviorDef(behavior_dict.get("instruction", ""), behavior_dict.get("frequency", "occasional"), tuple(behavior_dict.get("preferred_positions", []))),
            status="pending",
            source_type="private_chat_extraction",
            source_event_id=source_event.event_id if source_event else "system_private_chat",
            confirmed_by="",
            supersedes_id=superseded.directive_id if superseded else None,
        )
        MEMORY.add_behavioral_directive(directive)
        pending_behavioral.append(directive.to_dict())
    evidence_ids = tuple(item.evidence_id for item in observations) + tuple(item["evidence_id"] for item in citations)
    if evidence_ids:
        plan = replace(plan, evidence_ids=tuple(dict.fromkeys((*plan.evidence_ids, *evidence_ids)))[:32],
                       confidence=min((plan.confidence, *(item.confidence for item in observations))))
    metadata = {"channel": "private_chat", "observation_count": len(observations),
                "evidence_ids": list(evidence_ids), "knowledge_source": ETEYVAT.source_id if citations else None,
                "knowledge_revision": ETEYVAT.revision if citations else None, "citations": citations,
                "memory_proposals": pending_proposals, "behavioral_proposals": pending_behavioral}
    return plan, metadata


class Handler(BaseHTTPRequestHandler):
    server_version = "SiduriFoundation/0.1"

    def log_message(self, fmt: str, *args: object) -> None:
        LOG.info("%s - %s", self.address_string(), fmt % args)

    def _json(self, status: int, body: dict[str, Any]) -> None:
        raw = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        origin = self.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.end_headers()
        self.wfile.write(raw)

    def _check_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin or origin not in ALLOWED_ORIGINS:
            self.send_response(HTTPStatus.FORBIDDEN)
            self.send_header("Content-Length", "0")
            if origin in ALLOWED_ORIGINS:
                self.send_header("Access-Control-Allow-Origin", origin)
            self.end_headers()
            return False
        return True

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        origin = self.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        value = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(value, dict):
            raise ValueError("request body must be a JSON object")
        return value

    def do_GET(self) -> None:  # noqa: N802
        if not self._check_origin():
            return
        parsed_path = urlparse(self.path)
        if parsed_path.path.startswith("/platforms/oauth/"):
            parts = parsed_path.path.strip("/").split("/")
            if len(parts) == 4 and parts[1] == "oauth" and parts[3] == "start":
                provider_id = parts[2]
                try:
                    redirect_uri = parse_qs(parsed_path.query).get("redirect_uri", [os.getenv(f"SIDURI_{provider_id.upper()}_OAUTH_REDIRECT_URI", f"http://127.0.0.1:8765/platforms/oauth/{provider_id}/callback")])[0]
                    self.send_response(302)
                    self.send_header("Location", OAUTH_FLOWS.begin(provider_id, redirect_uri))
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                except (KeyError, ValueError) as error:
                    self._json(400, {"error": str(error)})
                return
            if len(parts) == 4 and parts[1] == "oauth" and parts[3] == "callback":
                provider_id = parts[2]
                query = parse_qs(parsed_path.query)
                try:
                    redirect_uri = query.get("redirect_uri", [os.getenv(f"SIDURI_{provider_id.upper()}_OAUTH_REDIRECT_URI", f"http://127.0.0.1:8765/platforms/oauth/{provider_id}/callback")])[0]
                    token = OAUTH_FLOWS.complete(provider_id, query.get("code", [""])[0], query.get("state", [""])[0], redirect_uri)
                    refresh_platform_sender(provider_id, token)
                    self._json(200, {"authorized": True, "provider": provider_id, "expires_in": token.expires_in})
                except (KeyError, ValueError) as error:
                    self._json(400, {"authorized": False, "error": str(error)})
                return
        if self.path == "/health":
            self._json(200, {"status": "ok"})
        elif self.path == "/ready":
            self._json(200, {"status": "ready", "dependencies": {"model_provider": configured_provider_state(MODEL_CONFIG, bool(os.getenv("ZAI_API_KEY")) if MODEL_PROVIDER == "zai" else True), "memory": {"provider_id": "supabase-postgres", "persistent": MEMORY_PERSISTENT}, "eteyvat": {"provider_id": ETEYVAT.source_id, "configured": True}, "voice": {"provider_id": VOICE_PROVIDER.provider_id, "enabled": VOICE_ENABLED}}})
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
        elif self.path == "/memory/claims":
            self._json(200, {"claims": [claim.to_dict() for claim in MEMORY.claims()]})
        elif self.path == "/memory/proposals":
            self._json(200, {"proposals": [memory_dict(proposal) for proposal in MEMORY.proposals()]})
        elif self.path == "/memory/audit":
            self._json(200, {"events": list(MEMORY.audit_events())})
        elif self.path == "/memory/behavioral":
            self._json(200, {"directives": [d.to_dict() for d in MEMORY.list_all_behavioral_directives()]})
        elif self.path == "/observations":
            self._json(200, {"observations": [item.to_dict() for item in current_observations(OBSERVATIONS)]})
        elif self.path == "/platforms/status":
            self._json(200, {"platforms": {
                platform.value: {"configured": platform in PLATFORM_SENDERS, "receive_mode": "adapter_boundary", "send_requires_approval": True}
                for platform in Platform
            }})
        elif self.path == "/platforms/events":
            self._json(200, {"events": [event.to_dict() for event in PLATFORM_EVENTS.events()]})
        elif self.path == "/platforms/actions":
            self._json(200, {"actions": [action.to_dict() for action in PLATFORM_ACTIONS.list()]})
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
            parsed_path = urlparse(self.path)
            if parsed_path.path.startswith("/platforms/oauth/"):
                parts = parsed_path.path.strip("/").split("/")
                if len(parts) == 4 and parts[1] == "oauth" and parts[3] == "refresh":
                    provider_id = parts[2]
                    refreshed = OAUTH_FLOWS.refresh(provider_id)
                    refresh_platform_sender(provider_id, refreshed)
                    self._json(200, {"refreshed": True, "provider": provider_id, "expires_in": refreshed.expires_in})
                    return
                if len(parts) == 4 and parts[1] == "oauth" and parts[3] == "revoke":
                    provider_id = parts[2]
                    OAUTH_FLOWS.revoke(provider_id)
                    OAUTH_TOKENS.pop(provider_id, None)
                    PLATFORM_SENDERS.pop(Platform(provider_id), None)
                    self._json(200, {"revoked": True, "provider": provider_id})
                    return
            if self.path == "/dev/mock-response":
                knowledge = ()
                if os.getenv("SIDURI_ETEYVAT_ENABLED", "true").lower() == "true":
                    try:
                        knowledge = tuple((item.title, item.content[:1200], item.url, item.revision) for item in ETEYVAT.search("Genshin Impact", limit=3))
                    except EteyvatError:
                        TELEMETRY.record("knowledge_failure", provider_id=ETEYVAT.source_id)
                assembler = PromptAssembler(ME_PROFILE)
                context = PromptContext(
                    recipient=Recipient.MASTER_STREAM,
                    user_text="foundation mock request",
                    memories=MEMORY.retrieve_claims("foundation mock", Recipient.MASTER_STREAM),
                    knowledge=knowledge,
                    behavioral_directives=MEMORY.list_active_behavioral_directives(),
                )
                plan = ROUTER.generate(GenerationRequest(
                    task="system_commentary",
                    prompt=assembler.context_prompt(context),
                    system_prompt=assembler.system_prompt(context),
                    recipient="master_stream",
                ))
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
                correlation_id = f"corr_{uuid4().hex}"
                observation_event = EventEnvelope("ObservationCreated", result.observation.to_dict(), source="observation", privacy_class="private", correlation_id=correlation_id)
                broadcast({"type": "observation", "event": observation_event.to_dict()})
                plan, metadata, _prompt = grounded_response(result.observation, correlation_id)
                stage_response(plan, metadata)
                response_event = EventEnvelope("ResponsePlanCreated", plan.to_dict(), correlation_id=correlation_id)
                broadcast({"type": "response_pending", "event": response_event.to_dict(), "metadata": metadata})
                self._json(202, {"accepted": True, "observation": observation_event.to_dict(), "response": response_event.to_dict(), "metadata": metadata})
            elif self.path == "/dev/observe-and-respond":
                result = OBSERVATION_SERVICE.observe_now()
                if result.observation is None:
                    self._json(409, {"accepted": False, "reason": result.capture_reason, "duplicate": result.duplicate})
                    return
                correlation_id = f"corr_{uuid4().hex}"
                observation_event = EventEnvelope("ObservationCreated", result.observation.to_dict(), source="observation", privacy_class="private", correlation_id=correlation_id)
                broadcast({"type": "observation", "event": observation_event.to_dict()})
                plan, metadata, _prompt = grounded_response(result.observation, correlation_id)
                stage_response(plan, metadata)
                response_event = EventEnvelope("ResponsePlanCreated", plan.to_dict(), correlation_id=correlation_id)
                broadcast({"type": "response_pending", "event": response_event.to_dict(), "metadata": metadata})
                self._json(202, {"accepted": True, "observation": observation_event.to_dict(), "response": response_event.to_dict(), "metadata": metadata})
            elif self.path == "/dev/approve-response":
                correlation_id = str(self._body().get("correlation_id", ""))
                plan, metadata = approve_response(correlation_id)
                response_event = EventEnvelope("ResponsePlanCreated", plan.to_dict(), correlation_id=correlation_id)
                broadcast({"type": "response_plan", "event": response_event.to_dict()})
                queue_voice(plan)
                self._json(200, {"approved": True, "response": response_event.to_dict(), "metadata": metadata})
            elif self.path == "/chat":
                plan, metadata = private_chat_response(self._body())
                self._json(200, {"response": plan.to_dict(), "metadata": metadata})
            elif self.path == "/dev/platform-event":
                event = platform_event_from_body(self._body())
                accepted = PLATFORM_EVENTS.ingest(event)
                self._json(202 if accepted else 200, {"accepted": accepted, "event": event.to_dict()})
            elif self.path == "/platforms/actions":
                body = self._body()
                action = OutboundAction(
                    platform=Platform(str(body["platform"])), action_type=str(body.get("action_type", "chat_message")),
                    target_id=str(body["target_id"]), text=str(body["text"]),
                    evidence_ids=tuple(str(item) for item in body.get("evidence_ids", [])),
                )
                self._json(202, {"action": PLATFORM_ACTIONS.propose(action).to_dict()})
            elif self.path == "/platforms/actions/suggest":
                body = self._body()
                plan, action = platform_reply_suggestion(str(body["event_id"]), str(body.get("language", "en")))
                self._json(202, {"suggested": True, "response": plan.to_dict(), "action": action.to_dict()})
            elif self.path == "/platforms/actions/approve":
                body = self._body()
                action = PLATFORM_ACTIONS.approve(str(body["action_id"]), str(body["text"]) if "text" in body else None)
                self._json(200, {"action": action.to_dict()})
            elif self.path == "/platforms/actions/reject":
                action = PLATFORM_ACTIONS.reject(str(self._body()["action_id"]))
                self._json(200, {"action": action.to_dict()})
            elif self.path == "/platforms/actions/send":
                action_id = str(self._body()["action_id"])
                action = PLATFORM_ACTIONS.get(action_id)
                if action is None:
                    raise KeyError(action_id)
                sender = PLATFORM_SENDERS.get(action.platform)
                if sender is None:
                    self._json(503, {"sent": False, "error": "platform_sender_not_configured"})
                    return
                sent, receipt = PLATFORM_ACTIONS.send(action_id, sender)
                self._json(200, {"sent": True, "receipt": receipt, "action": sent.to_dict()})
            elif self.path == "/memory":
                body = self._body()
                item = MEMORY.create(MemoryItem(content=str(body["content"]), provenance=str(body["provenance"]), sensitivity=str(body.get("sensitivity", "private")), allowed_audiences=frozenset(body.get("allowed_audiences", []))))
                self._json(201, {"item": memory_dict(item)})
            elif self.path == "/memory/proposals":
                body = self._body()
                proposal = MEMORY.propose(MemoryProposal(
                    content=str(body["content"]),
                    provenance=str(body["provenance"]),
                    sensitivity=str(body.get("sensitivity", "private")),
                    allowed_audiences=frozenset(body.get("allowed_audiences", [])),
                    subject=str(body.get("subject", "primary_user")),
                    predicate=str(body.get("predicate", "note")),
                    value=str(body["value"]) if body.get("value") is not None else None,
                    claim_type=str(body.get("claim_type", "semantic")),
                ))
                self._json(202, {"proposal": memory_dict(proposal)})
            elif self.path == "/dev/memory/reset":
                MEMORY.reset()
                self._json(200, {"reset": True})
            elif self.path == "/memory/proposals/approve":
                proposal = MEMORY.approve(str(self._body()["proposal_id"]))
                self._json(200, {"item": memory_dict(proposal)})
            elif self.path == "/memory/proposals/reject":
                proposal = MEMORY.reject(str(self._body()["proposal_id"]))
                self._json(200, {"proposal": memory_dict(proposal)})
            elif self.path == "/memory/proposals/update":
                body = self._body()
                audiences = body.get("allowed_audiences")
                proposal = MEMORY.update_proposal(
                    str(body["proposal_id"]), content=str(body["content"]),
                    sensitivity=str(body["sensitivity"]) if "sensitivity" in body else None,
                    allowed_audiences=frozenset(audiences) if isinstance(audiences, list) else None,
                )
                self._json(200, {"proposal": memory_dict(proposal)})
            elif self.path == "/memory/behavioral/approve":
                directive = MEMORY.approve_behavioral_directive(str(self._body()["directive_id"]))
                self._json(200, {"directive": directive.to_dict()})
            elif self.path == "/memory/behavioral/reject":
                directive = MEMORY.reject_behavioral_directive(str(self._body()["directive_id"]))
                self._json(200, {"directive": directive.to_dict()})
            elif self.path == "/memory/behavioral/disable":
                directive = MEMORY.disable_behavioral_directive(str(self._body()["directive_id"]))
                self._json(200, {"directive": directive.to_dict()})
            elif self.path == "/memory/behavioral/revoke":
                directive = MEMORY.revoke_behavioral_directive(str(self._body()["directive_id"]))
                self._json(200, {"directive": directive.to_dict()})
            else:
                self._json(404, {"error": "not_found"})
        except (KeyError, TypeError, ValueError) as error:
            self._json(400, {"error": str(error)})
        except ProviderUnavailableError as error:
            self._json(503, {"error": str(error)})
        except Exception as error:  # Keep one failed operation from dropping the proxy socket.
            LOG.exception("Unhandled POST %s failure", self.path)
            self._json(500, {
                "error": "Siduri could not complete this request.",
                "detail": type(error).__name__,
            })

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
    if not MEMORY_PERSISTENT:
        raise RuntimeError(
            "Supabase memory is required. Set SIDURI_SUPABASE_DATABASE_URL "
            "after applying migrations/002_memory.sql."
        )
    host = os.getenv("SIDURI_HOST", "127.0.0.1")
    port = int(os.getenv("SIDURI_PORT", "8765"))
    server = ThreadingHTTPServer((host, port), Handler)
    LOG.info("Siduri orchestrator listening on http://%s:%d", host, port)
    start_platform_workers()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOG.info("shutting down")
    finally:
        stop_platform_workers()
        server.server_close()


if __name__ == "__main__":
    main()
