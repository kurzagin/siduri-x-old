from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import socket
import threading
from pathlib import Path
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .contracts import EventEnvelope, MockProvider
from packages.config.env import load_dotenv
from packages.memory.service import MemoryItem, MemoryProposal, MemoryService
from packages.model_router.router import GenerationRequest, MockStructuredProvider, ModelRouter
from packages.model_router.zai import ZaiProviderError, ZaiStructuredProvider
from packages.persona.domain import MeProfile, Recipient
from packages.persona.prompt import PromptAssembler, PromptContext

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
MODEL_PROVIDER = os.getenv("SIDURI_MODEL_PROVIDER", "zai" if os.getenv("ZAI_API_KEY") else "mock")
MODEL_NAME = os.getenv("SIDURI_MODEL_NAME", "glm-5.2")
if MODEL_PROVIDER == "zai" and os.getenv("ZAI_API_KEY"):
    ROUTER = ModelRouter((ZaiStructuredProvider(os.environ["ZAI_API_KEY"], model=MODEL_NAME, base_url=os.getenv("ZAI_API_BASE_URL", "https://api.z.ai/api/paas/v4")), MockStructuredProvider()))
else:
    ROUTER = ModelRouter((MockStructuredProvider(),))


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
            self._json(200, {"status": "ready", "dependencies": {"model_provider": MODEL_PROVIDER, "model": MODEL_NAME}})
        elif self.path == "/version":
            self._json(200, {"name": "siduri-orchestrator", "version": VERSION})
        elif self.path == "/me":
            self._json(200, ME_PROFILE.to_dict())
        elif self.path == "/memory":
            self._json(200, {"items": [memory_dict(item) for item in MEMORY.list()]})
        elif self.path == "/memory/proposals":
            self._json(200, {"proposals": [memory_dict(proposal) for proposal in MEMORY.proposals()]})
        elif self.path == "/memory/audit":
            self._json(200, {"events": list(MEMORY.audit_events())})
        elif self.path == "/ws":
            self._websocket()
        else:
            self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        try:
            if self.path == "/dev/mock-response":
                prompt = PromptAssembler(ME_PROFILE).assemble(PromptContext(recipient=Recipient.MASTER_STREAM, user_text="foundation mock request", memories=MEMORY.retrieve("foundation mock", Recipient.MASTER_STREAM)))
                plan = ROUTER.generate(GenerationRequest(task="system_commentary", prompt=prompt, recipient="master_stream"))
                event = EventEnvelope(event_type="ResponsePlanCreated", payload=plan.to_dict())
                broadcast({"type": "response_plan", "event": event.to_dict()})
                self._json(202, {"accepted": True, "event": event.to_dict()})
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
