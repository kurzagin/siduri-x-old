from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import socket
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .contracts import EventEnvelope, MockProvider

LOG = logging.getLogger("siduri.orchestrator")
CLIENTS: set[socket.socket] = set()
CLIENTS_LOCK = threading.Lock()
PROVIDER = MockProvider()
VERSION = os.getenv("SIDURI_VERSION", "0.1.0-foundation")


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

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._json(200, {"status": "ok"})
        elif self.path == "/ready":
            self._json(200, {"status": "ready", "dependencies": {"mock_provider": "ready"}})
        elif self.path == "/version":
            self._json(200, {"name": "siduri-orchestrator", "version": VERSION})
        elif self.path == "/ws":
            self._websocket()
        else:
            self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/dev/mock-response":
            self._json(404, {"error": "not_found"})
            return
        plan = PROVIDER.response()
        event = EventEnvelope(event_type="ResponsePlanCreated", payload=plan.to_dict())
        broadcast({"type": "response_plan", "event": event.to_dict()})
        self._json(202, {"accepted": True, "event": event.to_dict()})

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
