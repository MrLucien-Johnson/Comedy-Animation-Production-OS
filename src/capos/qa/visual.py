"""Visual QA helpers — perceptual hash + honest REVIEW_REQUIRED."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from capos.core.schemas import QACheckResult
from capos.core.status import QAResultStatus


def average_hash(path: Path, hash_size: int = 8) -> str:
    """Simple aHash — not a claim of character identity."""
    img = Image.open(path).convert("L").resize((hash_size, hash_size), Image.Resampling.LANCZOS)
    pixels = list(img.getdata())
    avg = sum(pixels) / len(pixels)
    bits = "".join("1" if p >= avg else "0" for p in pixels)
    return f"{int(bits, 2):0{hash_size * hash_size // 4}x}"


def hamming_distance(h1: str, h2: str) -> int:
    b1 = bin(int(h1, 16))[2:].zfill(len(h1) * 4)
    b2 = bin(int(h2, 16))[2:].zfill(len(h2) * 4)
    return sum(c1 != c2 for c1, c2 in zip(b1, b2, strict=False))


def perceptual_similarity_check(
    image_a: Path | None,
    image_b: Path | None,
    *,
    check_id: str = "VISUAL_SIMILARITY",
    max_distance: int = 10,
) -> QACheckResult:
    """
    Compare average hashes. Even a close match is REVIEW_REQUIRED —
    never claim character identity definitely matches from aHash alone.
    """
    if image_a is None or image_b is None:
        return QACheckResult(
            check_id=check_id,
            status=QAResultStatus.NOT_CHECKED,
            message="Missing image path(s) for perceptual comparison",
        )
    if not Path(image_a).is_file() or not Path(image_b).is_file():
        return QACheckResult(
            check_id=check_id,
            status=QAResultStatus.FAIL,
            message="One or both images missing on disk",
        )
    try:
        ha = average_hash(Path(image_a))
        hb = average_hash(Path(image_b))
        dist = hamming_distance(ha, hb)
    except Exception as exc:  # noqa: BLE001
        return QACheckResult(
            check_id=check_id,
            status=QAResultStatus.NOT_CHECKED,
            message=f"Hash failed: {exc}",
        )
    if dist > max_distance:
        return QACheckResult(
            check_id=check_id,
            status=QAResultStatus.REQUIRES_HUMAN_REVIEW,
            message=f"Perceptual distance {dist} > {max_distance} — likely drift; human review",
            details={"hash_a": ha, "hash_b": hb, "distance": dist},
        )
    return QACheckResult(
        check_id=check_id,
        status=QAResultStatus.REQUIRES_HUMAN_REVIEW,
        message=(
            f"Perceptual distance {dist} within heuristic band — "
            "NOT a definitive identity match; human review required"
        ),
        details={"hash_a": ha, "hash_b": hb, "distance": dist, "identity_claimed": False},
    )


def palette_summary(path: Path, colors: int = 5) -> list[tuple[int, int, int]]:
    img = Image.open(path).convert("RGB").resize((64, 64))
    # Adaptive palette quantization
    quantized = img.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette() or []
    out = []
    for i in range(colors):
        r, g, b = palette[i * 3 : i * 3 + 3]
        out.append((r, g, b))
    return out


def palette_check(
    image_path: Path | None,
    reference_path: Path | None,
    *,
    check_id: str = "PALETTE_CHECK",
) -> QACheckResult:
    if not image_path or not reference_path:
        return QACheckResult(
            check_id=check_id,
            status=QAResultStatus.NOT_CHECKED,
            message="Palette comparison requires both images",
        )
    if not Path(image_path).is_file() or not Path(reference_path).is_file():
        return QACheckResult(
            check_id=check_id,
            status=QAResultStatus.NOT_CHECKED,
            message="Missing file(s) for palette comparison",
        )
    try:
        a = palette_summary(Path(image_path))
        b = palette_summary(Path(reference_path))
    except Exception as exc:  # noqa: BLE001
        return QACheckResult(
            check_id=check_id,
            status=QAResultStatus.NOT_CHECKED,
            message=str(exc),
        )
    return QACheckResult(
        check_id=check_id,
        status=QAResultStatus.REQUIRES_HUMAN_REVIEW,
        message="Palette sampled — heuristic only; human review required",
        details={"image_palette": a, "reference_palette": b},
    )
