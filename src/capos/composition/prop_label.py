"""Deterministic COOKIES prop label compositing."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from capos.core.schemas import COOKIE_LABEL_EXACT
from capos.qa.validators import assert_cookie_label_exact


def _font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except Exception:
        return ImageFont.load_default()


def apply_cookies_label(
    image_path: Path,
    output_path: Path,
    *,
    label: str = COOKIE_LABEL_EXACT,
    box: tuple[int, int, int, int] | None = None,
) -> str:
    """Composite exact COOKIES label onto a text-free jar render."""
    assert_cookie_label_exact(label)
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    if box is None:
        # Center band of jar — approximate mid-frame
        box = (int(w * 0.35), int(h * 0.42), int(w * 0.65), int(h * 0.55))
    x0, y0, x1, y1 = box
    draw.rectangle([x0, y0, x1, y1], fill=(245, 240, 230), outline=(30, 20, 15), width=3)
    font = _font(max(16, (x1 - x0) // 5))
    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = x0 + (x1 - x0 - tw) // 2
    ty = y0 + (y1 - y0 - th) // 2
    draw.text((tx, ty), label, font=font, fill=(20, 15, 10))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path)
    return label
