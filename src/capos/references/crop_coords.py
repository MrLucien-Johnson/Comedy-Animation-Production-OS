"""Display ↔ original crop coordinate mapping for Phase 2B.1 visual cropper.

ROOT CAUSE of the previous mismatch
-----------------------------------
The Streamlit UI showed the 1254×1254 source with ``st.image`` (browser-scaled to
the layout column width) while ``number_input`` crop values were applied with
``PIL.Image.crop`` on the **full-resolution** source.

Operators therefore estimated positions against the *displayed* thumbnail, but
those numbers were interpreted as *original* pixels. Defaults of
``right=min(sw, 256)`` / ``bottom=min(sh, 512)`` further selected the upper-left
logo region of the character sheet.

There was no 512×512 normalization and no EXIF flip in the crop path — the
failure was pure display-vs-original scale confusion (CSS/layout size ≠ file
pixels).

streamlit-cropper resizes for display (max 700×700 by default) and scales the
selected rectangle back to original pixels. CAPOS mirrors that math explicitly
so we can test and audit the mapping.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageOps

from capos.core.errors import ValidationError


DEFAULT_MAX_DISPLAY = 700


@dataclass(frozen=True)
class DisplayScale:
    original_width: int
    original_height: int
    display_width: int
    display_height: int
    scale_x: float  # original / display
    scale_y: float

    @property
    def as_dict(self) -> dict[str, float | int]:
        return {
            "original_width": self.original_width,
            "original_height": self.original_height,
            "display_width": self.display_width,
            "display_height": self.display_height,
            "scale_x": self.scale_x,
            "scale_y": self.scale_y,
        }


def open_rgb_corrected(path) -> Image.Image:
    """Open image as RGB with EXIF orientation applied (does not rewrite file)."""
    with Image.open(path) as img:
        corrected = ImageOps.exif_transpose(img)
        return corrected.convert("RGB")


def compute_display_scale(
    original_width: int,
    original_height: int,
    *,
    max_width: int = DEFAULT_MAX_DISPLAY,
    max_height: int = DEFAULT_MAX_DISPLAY,
) -> DisplayScale:
    """Mirror streamlit-cropper ``_resize_img`` sizing (height first, then width)."""
    if original_width < 1 or original_height < 1:
        raise ValidationError("Original image dimensions must be positive")
    w, h = int(original_width), int(original_height)
    if h > max_height:
        ratio = max_height / h
        w = int(w * ratio)
        h = int(h * ratio)
    if w > max_width:
        ratio = max_width / w
        w = int(w * ratio)
        h = int(h * ratio)
    w = max(1, w)
    h = max(1, h)
    return DisplayScale(
        original_width=int(original_width),
        original_height=int(original_height),
        display_width=w,
        display_height=h,
        scale_x=original_width / w,
        scale_y=original_height / h,
    )


def map_display_box_to_original(
    *,
    left: float,
    top: float,
    width: float,
    height: float,
    scale: DisplayScale,
) -> dict[str, int]:
    """Map a cropper rectangle from display pixels → original image pixels (PIL exclusive right/bottom)."""
    if width <= 0 or height <= 0:
        raise ValidationError("Display crop box must have positive width and height")
    left_o = int(round(left * scale.scale_x))
    top_o = int(round(top * scale.scale_y))
    width_o = int(round(width * scale.scale_x))
    height_o = int(round(height * scale.scale_y))
    left_o = max(0, left_o)
    top_o = max(0, top_o)
    right_o = min(scale.original_width, left_o + width_o)
    bottom_o = min(scale.original_height, top_o + height_o)
    if right_o <= left_o or bottom_o <= top_o:
        raise ValidationError("Mapped crop box is empty after clamping to original bounds")
    return {
        "left": left_o,
        "top": top_o,
        "right": right_o,
        "bottom": bottom_o,
        "width": right_o - left_o,
        "height": bottom_o - top_o,
        "display_box": {
            "left": float(left),
            "top": float(top),
            "width": float(width),
            "height": float(height),
        },
        "scale": scale.as_dict,
    }


def box_dict_to_pil_crop(box: dict[str, Any]) -> tuple[int, int, int, int]:
    """Accept either left/top/width/height or left/top/right/bottom."""
    if "right" in box and "bottom" in box:
        return int(box["left"]), int(box["top"]), int(box["right"]), int(box["bottom"])
    left = int(box["left"])
    top = int(box["top"])
    return left, top, left + int(box["width"]), top + int(box["height"])


COORDINATE_MISMATCH_CAUSE = (
    "Display-vs-original scale confusion: st.image showed a browser-scaled preview of the "
    "1254×1254 sheet while number_input values were applied as original-file pixels via "
    "PIL.crop. Defaults right≤256/bottom≤512 selected the upper-left logo. "
    "Not caused by 512×512 normalization or EXIF orientation."
)
