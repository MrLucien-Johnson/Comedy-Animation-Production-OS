"""ComfyUI smoke test + sequential style-master generation (Phase 2A)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from capos.canon.pipeline import CanonCreationPipeline
from capos.core.paths import project_root
from capos.core.schemas import utcnow
from capos.generation.comfyui_backend import ComfyUIBackend
from capos.generation.concurrency import generation_slot
from capos.generation.image_validate import validate_candidate_image
from capos.generation.provider_status import comfyui_dashboard_panel
from capos.hardware.profile import load_hardware_profile, resolve_generation_settings
from capos.production.storage import ensure_production_tree, register_production_file

SMOKE_PROMPT = (
    "fictional family-friendly 2D animated comedy still, warm Caribbean atmosphere, "
    "bold clean dark outlines, flat shading, warm earthy palette, subtle vintage texture, "
    "clean readable silhouette, simple-animation-friendly, professional cartoon series look, "
    "no text, no logos, no watermarks, no photorealism, no 3D CGI"
)
SMOKE_NEGATIVE = (
    "photorealistic, 3d render, anime, manga, hyper detailed, complex lighting, "
    "text, logo, watermark, celebrity, nsfw"
)


def run_provider_smoke_test(*, root: Path | None = None) -> dict[str, Any]:
    """One smoke image tagged PROVIDER_SMOKE_TEST — never canon."""
    root = root or project_root()
    panel = comfyui_dashboard_panel()
    if panel["status"] != "AVAILABLE" or not panel.get("connection_ok"):
        return {
            "ok": False,
            "tag": "PROVIDER_SMOKE_TEST",
            "canon": False,
            "reason": panel.get("reason") or "ComfyUI not available",
            "local_provider": panel.get("local_provider", "SETUP_REQUIRED"),
            "panel": panel,
        }
    if not panel.get("workflow_configured") and not os.environ.get("CAPOS_COMFYUI_WORKFLOW_PATH"):
        return {
            "ok": False,
            "tag": "PROVIDER_SMOKE_TEST",
            "canon": False,
            "reason": panel.get("workflow_reason") or "Workflow not production-configured",
            "local_provider": "SETUP_REQUIRED",
            "panel": panel,
        }
    if not panel.get("model"):
        return {
            "ok": False,
            "tag": "PROVIDER_SMOKE_TEST",
            "canon": False,
            "reason": "CAPOS_COMFYUI_CHECKPOINT not set",
            "local_provider": "SETUP_REQUIRED",
            "panel": panel,
        }

    hw = resolve_generation_settings(load_hardware_profile(root=root))
    out = (
        root
        / "production"
        / "likkle-jay"
        / "candidates"
        / "smoke"
        / f"provider-smoke-{utcnow().strftime('%Y%m%dT%H%M%SZ')}.png"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    backend = ComfyUIBackend()
    with generation_slot(root=root):
        result = backend.generate_image(
            prompt=SMOKE_PROMPT,
            negative_prompt=SMOKE_NEGATIVE,
            width=hw["width"],
            height=hw["height"],
            seed=42,
            output_path=out,
            settings={
                "smoke_test": True,
                "non_production": True,
                "workflow": "smoke-test.json",
                "candidate_id": "PROVIDER_SMOKE_TEST",
                "steps": hw.get("steps_hint"),
                "cfg": hw.get("cfg_hint"),
            },
        )
    if not result.success or not result.output_path:
        return {
            "ok": False,
            "tag": "PROVIDER_SMOKE_TEST",
            "canon": False,
            "reason": result.error or "smoke generation failed",
            "metadata": result.metadata,
            "local_provider": "AVAILABLE" if panel.get("connection_ok") else "SETUP_REQUIRED",
        }
    validation = validate_candidate_image(Path(result.output_path))
    if not validation["ok"]:
        return {
            "ok": False,
            "tag": "PROVIDER_SMOKE_TEST",
            "canon": False,
            "reason": validation.get("error"),
            "validation": validation,
        }
    meta = register_production_file(
        series_id="likkle-jay",
        category="smoke",
        asset_slug="provider-smoke",
        source_path=Path(result.output_path),
        root=root,
        kind="candidate",
    )
    return {
        "ok": True,
        "tag": "PROVIDER_SMOKE_TEST",
        "canon": False,
        "file": meta["file"],
        "checksum": meta["checksum"],
        "seed": result.seed,
        "model": result.model,
        "workflow": result.metadata.get("workflow"),
        "generation_resolution": result.metadata.get("generation_resolution"),
        "duration_ms": result.metadata.get("duration_ms"),
        "local_provider": "AVAILABLE",
        "note": "Smoke test only — not visual canon.",
    }


def run_style_master_three(*, root: Path | None = None) -> dict[str, Any]:
    """Generate exactly three style candidates sequentially after smoke OK path."""
    ensure_production_tree("likkle-jay", root=root)
    pipe = CanonCreationPipeline("likkle-jay", root=root)
    batch = pipe.generate_style_candidates(count=3)
    return {
        "batch": batch.model_dump(mode="json"),
        "status": batch.status.value if hasattr(batch.status, "value") else str(batch.status),
        "candidate_count": len(batch.candidates),
        "human_action": (
            "AWAITING_HUMAN_STYLE_SELECTION"
            if batch.candidates
            else "SETUP_OR_PROVIDER_FAILURE"
        ),
    }
