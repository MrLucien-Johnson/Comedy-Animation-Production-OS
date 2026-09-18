"""Deterministic text compositing — watermark, speech bubbles, covers."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from capos.core.schemas import WATERMARK_EXACT
from capos.qa.validators import assert_watermark_exact


def _font(size: int = 24) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except Exception:
        return ImageFont.load_default()


def apply_watermark(
    image_path: Path,
    output_path: Path,
    *,
    text: str = WATERMARK_EXACT,
    margin: int = 24,
) -> str:
    """Overlay exact watermark. Returns the text actually drawn."""
    assert_watermark_exact(text)
    img = Image.open(image_path).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _font(max(18, img.width // 40))
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = img.width - tw - margin
    y = img.height - th - margin
    # Subtle dark outline for readability
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0, 160))
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 200))
    composed = Image.alpha_composite(img, overlay).convert("RGB")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    composed.save(output_path)
    return text


def apply_speech_bubble(
    image_path: Path,
    output_path: Path,
    *,
    dialogue: str,
    box: tuple[int, int, int, int] | None = None,
) -> str:
    """
    Composite cream speech bubble with bold uppercase lettering.
    Returns the exact dialogue written (must match locked text).
    """
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    if box is None:
        # Top area bubble
        box = (int(w * 0.08), int(h * 0.05), int(w * 0.92), int(h * 0.28))
    x0, y0, x1, y1 = box
    # Cream / off-white fill, bold dark outline
    draw.rounded_rectangle(
        [x0, y0, x1, y1], radius=24, fill=(255, 248, 230), outline=(20, 15, 10), width=5
    )
    font = _font(max(20, w // 28))
    text = dialogue.upper()
    # Simple wrap
    words = text.split()
    lines: list[str] = []
    current = ""
    max_width = x1 - x0 - 40
    for word in words:
        trial = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    ty = y0 + 20
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        tx = x0 + (x1 - x0 - lw) // 2
        draw.text((tx, ty), line, font=font, fill=(10, 10, 10))
        ty += (bbox[3] - bbox[1]) + 8
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path)
    return dialogue


def compose_cover_title(
    image_path: Path,
    output_path: Path,
    *,
    series_title: str,
    season_episode: str,
    episode_title: str,
) -> Path:
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    # Bottom title plate
    draw.rectangle([0, int(h * 0.72), w, h], fill=(30, 20, 15))
    font_lg = _font(max(28, w // 16))
    font_sm = _font(max(18, w // 28))
    draw.text((40, int(h * 0.75)), series_title.upper(), font=font_lg, fill=(255, 220, 120))
    draw.text((40, int(h * 0.84)), season_episode.upper(), font=font_sm, fill=(255, 248, 230))
    draw.text((40, int(h * 0.90)), episode_title.upper(), font=font_lg, fill=(255, 248, 230))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path)
    return output_path
