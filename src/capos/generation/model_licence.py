"""Model licence / provenance — fail closed for production when unverified."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from capos.core.paths import config_dir, project_root

DEFAULT_MODEL_ID = "toonyou_beta6"


def models_dir(*, root: Path | None = None) -> Path:
    return config_dir(root=root or project_root()) / "models"


def load_model_provenance(
    model_id: str | None = None,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    """Load provenance JSON for a checkpoint family. Never invent VERIFIED."""
    mid = model_id or os.environ.get("CAPOS_COMFYUI_MODEL_ID") or DEFAULT_MODEL_ID
    path = models_dir(root=root) / f"{mid}.json"
    if not path.is_file():
        return {
            "model": os.environ.get("CAPOS_COMFYUI_CHECKPOINT") or mid,
            "model_id": mid,
            "licence_status": "UNVERIFIED",
            "commercial_use": "UNKNOWN",
            "error": f"Missing provenance file: {path}",
            "path": str(path),
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    # Env can override status only to VERIFIED when operator explicitly sets it
    env_status = os.environ.get("CAPOS_COMFYUI_MODEL_LICENCE_STATUS", "").strip().upper()
    if env_status in {"VERIFIED", "UNVERIFIED"}:
        data["licence_status"] = env_status
    env_note = os.environ.get("CAPOS_COMFYUI_MODEL_LICENCE")
    if env_note:
        data["licence_env_note"] = env_note
    data["path"] = str(path)
    data["model_id"] = mid
    return data


def licence_is_verified(prov: dict[str, Any] | None = None, *, root: Path | None = None) -> bool:
    prov = prov or load_model_provenance(root=root)
    return str(prov.get("licence_status", "UNVERIFIED")).upper() == "VERIFIED"


def production_licence_gate(*, root: Path | None = None) -> tuple[bool, str]:
    """Fail closed: production readiness requires VERIFIED licence status."""
    prov = load_model_provenance(root=root)
    status = str(prov.get("licence_status", "UNVERIFIED")).upper()
    if status != "VERIFIED":
        return (
            False,
            (
                f"MODEL_LICENCE_UNVERIFIED ({prov.get('model')}). "
                "Record verification in config/models/ and set "
                "CAPOS_COMFYUI_MODEL_LICENCE_STATUS=VERIFIED only after human review of source terms. "
                f"commercial_use={prov.get('commercial_use')}"
            ),
        )
    commercial = str(prov.get("commercial_use", "UNKNOWN")).upper()
    if commercial in {"FORBIDDEN", "UNKNOWN", "REQUIRES_AUTHOR_CONTACT"}:
        # VERIFIED status may still note contact-required; block season production until
        # operator records an allowed commercial determination.
        if not prov.get("commercial_use_operator_ack"):
            return (
                False,
                (
                    f"Commercial-use determination incomplete for {prov.get('model')}: "
                    f"{prov.get('commercial_use')}. Acknowledge/resolve before SEASON_PRODUCTION_READY."
                ),
            )
    return True, "ok"


def environment_runtime_status() -> dict[str, Any]:
    """Honest cloud vs production-machine distinction."""
    from capos.generation.comfyui_backend import ComfyUIBackend
    from capos.hardware.profile import detect_gpu

    gpu = detect_gpu()
    url = os.environ.get("CAPOS_COMFYUI_URL", "")
    ok, reason = ComfyUIBackend().available()
    if ok and gpu.get("detected"):
        mode = "PRODUCTION_MACHINE_LOCAL"
        local_status = "LOCAL_RUNTIME_VERIFIED" if ok else "SETUP_REQUIRED"
    elif ok:
        mode = "LOCAL_COMFYUI_REACHABLE"
        local_status = "LOCAL_RUNTIME_VERIFIED"
    else:
        mode = "ENGINEERING_ENVIRONMENT"
        local_status = "LOCAL_EXECUTION_REQUIRED"
    return {
        "engineering_environment": {
            "has_local_gpu": bool(gpu.get("detected")),
            "has_comfyui_access": ok,
            "note": "Cloud/agent environments typically have neither GPU nor the operator's ComfyUI.",
        },
        "production_machine": {
            "operator_manual_verification": (
                "LOCAL COMFYUI MANUALLY VERIFIED BY OPERATOR — "
                "toonyou_beta6.safetensors @ 512x512 SAFE settings (external to this environment)"
            ),
            "checkpoint": "toonyou_beta6.safetensors",
            "verified_settings": {
                "width": 512,
                "height": 512,
                "batch_size": 1,
                "steps": 20,
                "cfg": 7.0,
                "sampler": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
            },
        },
        "runtime_mode": mode,
        "local_provider_status": local_status,
        "comfyui_url_configured": bool(url),
        "comfyui_available": ok,
        "comfyui_reason": reason,
        "gpu": gpu,
    }
