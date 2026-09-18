"""Hardware / VRAM generation profiles — RTX 3050 6GB first-class."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from capos.core.paths import config_dir, project_root


class HardwareProfile(BaseModel):
    profile_id: str = "LOW_VRAM_6GB"
    vram_class: str = "LOW_6GB"
    vram_gb: float = 6.0
    gpu_name_hint: str = "NVIDIA GeForce RTX 3050"
    generation_concurrency: int = 1
    default_width: int = 512
    default_height: int = 512
    max_width: int = 640
    max_height: int = 640
    generation_profile: str = "SAFE"  # SAFE | BALANCED | QUALITY
    allow_parallel_jobs: bool = False
    oom_max_retries: int = 2
    oom_fallback_widths: list[int] = Field(default_factory=lambda: [512, 448, 384])
    prefer_reference_edit: bool = True
    notes: str = (
        "Designed for ~6 GB VRAM. Diffusion resolution is separate from export resolution. "
        "Default concurrency is 1. Do not stack large checkpoint + multiple ControlNets + "
        "high res + upscale simultaneously."
    )


GENERATION_PROFILES: dict[str, dict[str, Any]] = {
    "SAFE": {
        "width": 512,
        "height": 512,
        "steps_hint": 20,
        "cfg_hint": 7.0,
        "enable_quality_upscale": False,
        "reference_complexity": "low",
    },
    "BALANCED": {
        "width": 512,
        "height": 512,
        "steps_hint": 28,
        "cfg_hint": 7.0,
        "enable_quality_upscale": True,
        "reference_complexity": "medium",
    },
    "QUALITY": {
        "width": 640,
        "height": 640,
        "steps_hint": 30,
        "cfg_hint": 7.5,
        "enable_quality_upscale": True,
        "reference_complexity": "high",
        "requires_smoke_ok": True,
    },
}


def detect_gpu() -> dict[str, Any]:
    """Best-effort GPU detection. Never invent VRAM figures."""
    info: dict[str, Any] = {
        "detected": False,
        "name": None,
        "vram_mb": None,
        "source": None,
        "error": None,
    }
    try:
        import subprocess

        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=5,
        ).strip()
        if out:
            # e.g. "NVIDIA GeForce RTX 3050, 6144"
            parts = [p.strip() for p in out.split(",")]
            info["detected"] = True
            info["name"] = parts[0] if parts else None
            if len(parts) > 1:
                try:
                    info["vram_mb"] = float(parts[1])
                except ValueError:
                    info["vram_mb"] = None
            info["source"] = "nvidia-smi"
            return info
    except Exception as exc:  # noqa: BLE001
        info["error"] = str(exc)
    # Manual override via env
    if os.environ.get("CAPOS_GPU_NAME") or os.environ.get("CAPOS_VRAM_GB"):
        info["detected"] = True
        info["name"] = os.environ.get("CAPOS_GPU_NAME", "manual")
        gb = os.environ.get("CAPOS_VRAM_GB")
        info["vram_mb"] = float(gb) * 1024 if gb else None
        info["source"] = "env"
    return info


def default_low_vram_profile() -> HardwareProfile:
    return HardwareProfile()


def load_hardware_profile(*, root: Path | None = None) -> HardwareProfile:
    path = config_dir(root=root or project_root()) / "hardware.json"
    if path.is_file():
        return HardwareProfile.model_validate(json.loads(path.read_text(encoding="utf-8")))
    return default_low_vram_profile()


def save_hardware_profile(profile: HardwareProfile, *, root: Path | None = None) -> Path:
    path = config_dir(root=root or project_root()) / "hardware.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(profile.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8"
    )
    return path


def resolve_generation_settings(profile: HardwareProfile | None = None) -> dict[str, Any]:
    profile = profile or load_hardware_profile()
    gen = GENERATION_PROFILES.get(profile.generation_profile, GENERATION_PROFILES["SAFE"])
    width = min(int(gen["width"]), profile.max_width)
    height = min(int(gen["height"]), profile.max_height)
    # Force profile defaults for SAFE on 6GB
    if profile.generation_profile == "SAFE":
        width = profile.default_width
        height = profile.default_height
    return {
        "profile_id": profile.profile_id,
        "vram_class": profile.vram_class,
        "generation_profile": profile.generation_profile,
        "width": width,
        "height": height,
        "concurrency": 1 if not profile.allow_parallel_jobs else profile.generation_concurrency,
        "oom_max_retries": profile.oom_max_retries,
        "oom_fallback_widths": list(profile.oom_fallback_widths),
        "steps_hint": gen.get("steps_hint"),
        "cfg_hint": gen.get("cfg_hint"),
        "enable_quality_upscale": gen.get("enable_quality_upscale", False),
        "reference_complexity": gen.get("reference_complexity"),
        "notes": profile.notes,
    }


def assert_single_concurrency(profile: HardwareProfile | None = None) -> None:
    settings = resolve_generation_settings(profile)
    if settings["concurrency"] != 1 and settings["vram_class"] == "LOW_6GB":
        raise RuntimeError("LOW_6GB profile forbids concurrency != 1")
