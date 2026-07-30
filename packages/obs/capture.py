"""Safe OBS capture boundary.

The transport is intentionally injected. A real OBS WebSocket v5 client can be
added without allowing the rest of Siduri to depend on a websocket library or
on fixed scene names.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import base64
import hashlib
import json
import secrets
import socket
import struct
from typing import Protocol


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ObsStatus:
    connected: bool
    streaming: bool = False
    recording: bool = False
    capture_enabled: bool = False
    source_name: str | None = None


@dataclass(frozen=True)
class CaptureResult:
    frame: bytes | None
    source_name: str
    captured_at: str
    status: ObsStatus
    reason: str | None = None


class ObsTransport(Protocol):
    def status(self) -> ObsStatus: ...

    def screenshot(self, source_name: str) -> bytes: ...


class ObsCaptureBoundary:
    """Allow bounded still captures only while the local kill switch is on."""

    def __init__(self, transport: ObsTransport, *, source_name: str, enabled: bool = False) -> None:
        if not source_name.strip() or len(source_name) > 128:
            raise ValueError("OBS source_name must be a bounded non-empty string")
        self.transport = transport
        self.source_name = source_name
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> ObsStatus:
        self._enabled = enabled
        current = self.transport.status()
        return ObsStatus(current.connected, current.streaming, current.recording, enabled, self.source_name)

    def status(self) -> ObsStatus:
        current = self.transport.status()
        return ObsStatus(current.connected, current.streaming, current.recording, self._enabled, self.source_name)

    def capture_once(self) -> CaptureResult:
        status = self.status()
        if not self._enabled:
            return CaptureResult(None, self.source_name, _now(), status, "capture_disabled")
        if not status.connected:
            return CaptureResult(None, self.source_name, _now(), status, "obs_disconnected")
        try:
            frame = self.transport.screenshot(self.source_name)
        except (OSError, RuntimeError):
            return CaptureResult(None, self.source_name, _now(), status, "screenshot_failed")
        if not frame:
            return CaptureResult(None, self.source_name, _now(), status, "empty_screenshot")
        return CaptureResult(frame, self.source_name, _now(), status)


class FakeObsTransport:
    """Deterministic transport for tests and local fixture development."""

    def __init__(self, frame: bytes = b"fixture-frame", *, connected: bool = True,
                 streaming: bool = False, recording: bool = False) -> None:
        self.frame = frame
        self.connected = connected
        self.streaming = streaming
        self.recording = recording
        self.requests: list[str] = []

    def status(self) -> ObsStatus:
        return ObsStatus(self.connected, self.streaming, self.recording)

    def screenshot(self, source_name: str) -> bytes:
        self.requests.append(source_name)
        if not self.connected:
            raise OSError("not connected")
        return self.frame


class ObsWebSocketTransport:
    """Small OBS WebSocket v5 client for local status and still captures."""

    def __init__(self, url: str = "ws://127.0.0.1:4455", password: str | None = None,
                 *, timeout_seconds: float = 5.0) -> None:
        if not url.startswith("ws://"):
            raise ValueError("OBS WebSocket URL must use ws:// for local OBS")
        self.url = url
        self.password = password
        self.timeout_seconds = timeout_seconds
        self._socket: socket.socket | None = None
        self._request_id = 0

    def connect(self) -> None:
        if self._socket is not None:
            return
        target = self.url[5:]
        host_port, _, path = target.partition("/")
        host, separator, port = host_port.partition(":")
        sock = socket.create_connection((host, int(port) if separator else 80), self.timeout_seconds)
        sock.settimeout(self.timeout_seconds)
        key = base64.b64encode(secrets.token_bytes(16)).decode()
        request_path = "/" + path
        sock.sendall((f"GET {request_path} HTTP/1.1\r\nHost: {host_port}\r\nUpgrade: websocket\r\n"
                      f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        response = self._read_until(sock, b"\r\n\r\n")
        if not response.startswith(b"HTTP/1.1 101"):
            sock.close()
            raise RuntimeError("OBS WebSocket handshake failed")
        self._socket = sock
        hello = self._receive_json()
        if hello.get("op") != 0:
            raise RuntimeError("OBS did not send Hello")
        hello_data = hello.get("d", {})
        identify: dict[str, object] = {"rpcVersion": 1}
        authentication = hello_data.get("authentication") if isinstance(hello_data, dict) else None
        if authentication:
            if not self.password:
                self.close()
                raise RuntimeError("OBS WebSocket authentication is required")
            if not isinstance(authentication, dict):
                raise RuntimeError("OBS authentication payload is invalid")
            challenge = str(authentication.get("challenge", ""))
            salt = str(authentication.get("salt", ""))
            secret = base64.b64encode(hashlib.sha256((self.password + salt).encode()).digest()).decode()
            identify["authentication"] = base64.b64encode(hashlib.sha256((secret + challenge).encode()).digest()).decode()
        self._send_json({"op": 1, "d": identify})
        identified = self._receive_json()
        if identified.get("op") != 2:
            self.close()
            raise RuntimeError("OBS WebSocket identify failed")

    def close(self) -> None:
        if self._socket is not None:
            try:
                self._socket.close()
            finally:
                self._socket = None

    def status(self) -> ObsStatus:
        self.connect()
        stream = self._request("GetStreamStatus")
        record = self._request("GetRecordStatus")
        return ObsStatus(True, bool(stream.get("outputActive")), bool(record.get("outputActive")))

    def screenshot(self, source_name: str) -> bytes:
        self.connect()
        response = self._request("GetSourceScreenshot", {"sourceName": source_name, "imageFormat": "png"})
        image_data = response.get("imageData")
        if not isinstance(image_data, str) or "," not in image_data:
            raise RuntimeError("OBS returned no screenshot data")
        return base64.b64decode(image_data.split(",", 1)[1], validate=True)

    def _request(self, request_type: str, request_data: dict[str, object] | None = None) -> dict[str, object]:
        self._request_id += 1
        request_id = f"siduri-{self._request_id}"
        self._send_json({"op": 6, "d": {"requestType": request_type, "requestId": request_id, "requestData": request_data or {}}})
        while True:
            message = self._receive_json()
            if message.get("op") != 7:
                continue
            data = message.get("d", {})
            if not isinstance(data, dict) or data.get("requestId") != request_id:
                continue
            status = data.get("requestStatus", {})
            if not isinstance(status, dict) or status.get("result") is not True:
                raise RuntimeError(f"OBS request failed: {request_type}")
            value = data.get("responseData", {})
            return value if isinstance(value, dict) else {}

    def _send_json(self, value: dict[str, object]) -> None:
        if self._socket is None:
            raise RuntimeError("OBS WebSocket is not connected")
        payload = json.dumps(value, separators=(",", ":")).encode()
        mask = secrets.token_bytes(4)
        encoded = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        length = len(encoded)
        if length < 126:
            header = bytes((0x81, 0x80 | length))
        elif length < 65536:
            header = bytes((0x81, 0x80 | 126)) + struct.pack(">H", length)
        else:
            header = bytes((0x81, 0x80 | 127)) + struct.pack(">Q", length)
        self._socket.sendall(header + mask + encoded)

    def _receive_json(self) -> dict[str, object]:
        if self._socket is None:
            raise RuntimeError("OBS WebSocket is not connected")
        first, second = self._read_exact(self._socket, 2)
        opcode = first & 0x0F
        length = second & 0x7F
        if length == 126:
            length = struct.unpack(">H", self._read_exact(self._socket, 2))[0]
        elif length == 127:
            length = struct.unpack(">Q", self._read_exact(self._socket, 8))[0]
        mask = self._read_exact(self._socket, 4) if second & 0x80 else None
        payload = self._read_exact(self._socket, length)
        if mask:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        if opcode == 0x8:
            raise RuntimeError("OBS WebSocket closed")
        if opcode == 0x9:
            return self._receive_json()
        value = json.loads(payload.decode())
        if not isinstance(value, dict):
            raise RuntimeError("OBS WebSocket message is not an object")
        return value

    @staticmethod
    def _read_exact(sock: socket.socket, size: int) -> bytes:
        chunks: list[bytes] = []
        remaining = size
        while remaining:
            chunk = sock.recv(remaining)
            if not chunk:
                raise RuntimeError("OBS WebSocket disconnected")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    @staticmethod
    def _read_until(sock: socket.socket, marker: bytes) -> bytes:
        data = bytearray()
        while marker not in data:
            chunk = sock.recv(4096)
            if not chunk:
                raise RuntimeError("OBS WebSocket disconnected during handshake")
            data.extend(chunk)
        return bytes(data)
