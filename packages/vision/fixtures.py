"""Asset fixture loading with signature-based MIME detection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AssetImage:
    path: Path
    content: bytes
    mime_type: str


def _mime(content: bytes) -> str:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"RIFF") and b"WEBP" in content[:16]:
        return "image/webp"
    raise ValueError("unsupported image fixture format")


def load_asset_images(directory: str | Path) -> tuple[AssetImage, ...]:
    root = Path(directory)
    if not root.is_dir():
        raise ValueError("asset directory does not exist")
    images: list[AssetImage] = []
    for path in sorted(root.iterdir()):
        if path.is_file():
            content = path.read_bytes()
            try:
                images.append(AssetImage(path, content, _mime(content)))
            except ValueError:
                continue
    return tuple(images)
