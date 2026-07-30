import struct
import unittest
import zlib

from packages.observation.png import PixelRect, redact_png


def png(width: int, height: int, pixels: bytes) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    raw = b"".join(b"\x00" + pixels[row * width * 4 : (row + 1) * width * 4] for row in range(height))
    def chunk(kind: bytes, value: bytes) -> bytes:
        return struct.pack(">I", len(value)) + kind + value + struct.pack(">I", zlib.crc32(kind + value) & 0xFFFFFFFF)
    return signature + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


class PngRedactionTests(unittest.TestCase):
    def test_redacts_pixels_in_memory(self) -> None:
        source = png(2, 1, bytes((255, 0, 0, 255, 0, 255, 0, 255)))
        redacted = redact_png(source, (PixelRect(0, 0, 1, 1),))
        self.assertNotEqual(source, redacted)
        self.assertIn(b"IDAT", redacted)

    def test_rejects_unsupported_frame(self) -> None:
        with self.assertRaises(ValueError):
            redact_png(b"not-png", ())


if __name__ == "__main__":
    unittest.main()
