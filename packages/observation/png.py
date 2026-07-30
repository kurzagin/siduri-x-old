"""Dependency-free redaction for ordinary 8-bit RGB/RGBA PNG screenshots."""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass


@dataclass(frozen=True)
class PixelRect:
    left: int
    top: int
    right: int
    bottom: int

    def validate(self, width: int, height: int) -> None:
        if not (0 <= self.left < self.right <= width and 0 <= self.top < self.bottom <= height):
            raise ValueError("redaction rectangle is outside the image")


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def redact_png(image: bytes, regions: tuple[PixelRect, ...]) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    if not image.startswith(signature):
        raise ValueError("frame is not a PNG")
    position = len(signature)
    ihdr: bytes | None = None
    idat: list[bytes] = []
    ancillary: list[tuple[bytes, bytes]] = []
    while position < len(image):
        if position + 8 > len(image):
            raise ValueError("truncated PNG")
        size = struct.unpack(">I", image[position : position + 4])[0]
        kind = image[position + 4 : position + 8]
        payload_start = position + 8
        payload_end = payload_start + size
        if payload_end + 4 > len(image):
            raise ValueError("truncated PNG chunk")
        payload = image[payload_start:payload_end]
        position = payload_end + 4
        if kind == b"IHDR":
            ihdr = payload
        elif kind == b"IDAT":
            idat.append(payload)
        elif kind == b"IEND":
            break
        elif kind not in {b"PLTE", b"tRNS"}:
            ancillary.append((kind, payload))
    if ihdr is None or len(ihdr) != 13 or not idat:
        raise ValueError("PNG is missing image data")
    width, height, depth, color_type, compression, filtering, interlace = struct.unpack(">IIBBBBB", ihdr)
    if depth != 8 or color_type not in {2, 6} or compression != 0 or filtering != 0 or interlace != 0:
        raise ValueError("only non-interlaced 8-bit RGB/RGBA PNG is supported")
    channels = 4 if color_type == 6 else 3
    stride = width * channels
    decoded = zlib.decompress(b"".join(idat))
    expected = height * (stride + 1)
    if len(decoded) != expected:
        raise ValueError("PNG scanline data has unexpected length")
    rows: list[bytearray] = []
    offset = 0
    previous = bytearray(stride)
    for _ in range(height):
        filter_type = decoded[offset]
        raw = bytearray(decoded[offset + 1 : offset + 1 + stride])
        offset += stride + 1
        for index in range(stride):
            left = raw[index - channels] if index >= channels else 0
            up = previous[index]
            upper_left = previous[index - channels] if index >= channels else 0
            if filter_type == 1:
                raw[index] = (raw[index] + left) & 255
            elif filter_type == 2:
                raw[index] = (raw[index] + up) & 255
            elif filter_type == 3:
                raw[index] = (raw[index] + ((left + up) // 2)) & 255
            elif filter_type == 4:
                estimate = left + up - upper_left
                distances = (abs(estimate - left), abs(estimate - up), abs(estimate - upper_left))
                raw[index] = (raw[index] + (left, up, upper_left)[distances.index(min(distances))]) & 255
            elif filter_type != 0:
                raise ValueError("unsupported PNG filter")
        rows.append(raw)
        previous = raw
    for region in regions:
        region.validate(width, height)
        for y in range(region.top, region.bottom):
            row = rows[y]
            for x in range(region.left, region.right):
                start = x * channels
                row[start : start + channels] = b"\x00" * channels
    scanlines = b"".join(b"\x00" + bytes(row) for row in rows)
    output = [signature, _chunk(b"IHDR", ihdr)]
    output.extend(_chunk(kind, payload) for kind, payload in ancillary)
    output.append(_chunk(b"IDAT", zlib.compress(scanlines)))
    output.append(_chunk(b"IEND", b""))
    return b"".join(output)
