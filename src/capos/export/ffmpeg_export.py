"""FFmpeg-based assembly helpers — only claims success when outputs exist."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ReframeSpec(BaseModel):
    """Intelligent crop/reframe — never stretch."""

    source_aspect: str = "1:1"
    target_aspect: str = "1:1"
    crop_x: float = 0.0  # normalized
    crop_y: float = 0.0
    crop_w: float = 1.0
    crop_h: float = 1.0
    notes: str = ""


DEFAULT_REFRAMES: dict[str, ReframeSpec] = {
    "1:1": ReframeSpec(target_aspect="1:1"),
    "9:16": ReframeSpec(
        target_aspect="9:16",
        crop_x=0.125,
        crop_y=0.0,
        crop_w=0.75,
        crop_h=1.0,
        notes="Center-weighted vertical crop from square master",
    ),
    "16:9": ReframeSpec(
        target_aspect="16:9",
        crop_x=0.0,
        crop_y=0.125,
        crop_w=1.0,
        crop_h=0.75,
        notes="Center-weighted horizontal crop from square master",
    ),
    "4:5": ReframeSpec(
        target_aspect="4:5",
        crop_x=0.05,
        crop_y=0.0,
        crop_w=0.9,
        crop_h=1.0,
        notes="Slight side crop for 4:5",
    ),
}


class ExportRequest(BaseModel):
    episode_id: str
    frame_paths: list[str] = Field(default_factory=list)
    fps: int = 2
    target_aspect: str = "1:1"
    output_path: str
    audio_path: str | None = None
    subtitle_path: str | None = None
    human_override: bool = False
    qa_all_passed: bool = False


def ffmpeg_available() -> tuple[bool, str]:
    path = shutil.which("ffmpeg")
    if not path:
        return False, "ffmpeg not found on PATH"
    return True, path


def assemble_slideshow(req: ExportRequest) -> dict[str, Any]:
    """
    Assemble a simple slideshow MP4 from frame stills.
    Refuses unless QA passed or human override.
    """
    if not req.qa_all_passed and not req.human_override:
        return {
            "success": False,
            "error": "Export blocked: QA not all PASS and no human override",
            "output_path": None,
        }
    ok, ff = ffmpeg_available()
    if not ok:
        return {"success": False, "error": ff, "output_path": None}

    missing = [p for p in req.frame_paths if not Path(p).is_file()]
    if missing:
        return {
            "success": False,
            "error": f"Missing frame files: {missing}",
            "output_path": None,
        }
    if not req.frame_paths:
        return {"success": False, "error": "No frames to assemble", "output_path": None}

    out = Path(req.output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    list_file = out.with_suffix(".txt")
    # concat demuxer with duration per still
    lines = []
    duration = 1.0 / max(req.fps, 1)
    for p in req.frame_paths:
        lines.append(f"file '{Path(p).resolve()}'")
        lines.append(f"duration {duration}")
    lines.append(f"file '{Path(req.frame_paths[-1]).resolve()}'")
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    cmd = [
        ff,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-vsync",
        "vfr",
        "-pix_fmt",
        "yuv420p",
        str(out),
    ]
    if req.audio_path and Path(req.audio_path).is_file():
        cmd = [
            ff,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-i",
            req.audio_path,
            "-shortest",
            "-pix_fmt",
            "yuv420p",
            str(out),
        ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.is_file():
        return {
            "success": False,
            "error": proc.stderr[-2000:] if proc.stderr else "ffmpeg failed",
            "output_path": None,
        }

    result: dict[str, Any] = {
        "success": True,
        "output_path": str(out),
        "reframe": DEFAULT_REFRAMES.get(req.target_aspect, ReframeSpec()).model_dump(),
    }
    if req.subtitle_path and Path(req.subtitle_path).is_file():
        result["subtitle_path"] = req.subtitle_path
        result["subtitle_muxed"] = False
        result["note"] = "Subtitle file produced separately; mux optional in later pass"
    return result
