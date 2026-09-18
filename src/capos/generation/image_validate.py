"""Validate generated image files before claiming production success."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from capos.production.storage import sha256_file


def validate_candidate_image(
    path: Path,
    *,
    require_square: bool = True,
    min_side: int = 64,
) -> dict[str, Any]:
    """Confirm file exists, non-zero, decodes, dimensions OK. Fail closed."""
    result: dict[str, Any] = {
        "ok": False,
        "path": str(path),
        "bytes": 0,
        "width": None,
        "height": None,
        "square": False,
        "checksum": None,
        "error": None,
    }
    if not path.is_file():
        result["error"] = "FILE_MISSING"
        return result
    size = path.stat().st_size
    result["bytes"] = size
    if size <= 0:
        result["error"] = "ZERO_BYTES"
        return result
    try:
        with Image.open(path) as img:
            img.load()
            w, h = img.size
            result["width"] = w
            result["height"] = h
            result["square"] = w == h
            if w < min_side or h < min_side:
                result["error"] = "DIMENSION_TOO_SMALL"
                return result
            if require_square and w != h:
                result["error"] = "NOT_SQUARE"
                return result
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"DECODE_FAILED: {exc}"
        return result
    result["checksum"] = sha256_file(path)
    result["ok"] = True
    return result
