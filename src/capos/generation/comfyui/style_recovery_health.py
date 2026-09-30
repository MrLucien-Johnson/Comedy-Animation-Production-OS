"""Phase 2B ComfyUI img2img health checks — fail closed; never fall back to txt2img/mock."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from capos.generation.comfyui.client import ComfyUIClient
from capos.generation.comfyui.validate import validate_api_workflow
from capos.generation.comfyui.workflows import describe_workflow, load_workflow, workflow_is_configured

STYLE_RECOVERY_WORKFLOW = "style-recovery-img2img-low-vram.json"
REQUIRED_NODE_TYPES = (
    "CheckpointLoaderSimple",
    "CLIPTextEncode",
    "LoadImage",
    "VAEEncode",
    "KSampler",
    "VAEDecode",
    "SaveImage",
)
MAX_STYLE_RECOVERY_DENOISE = 0.45
MIN_STYLE_RECOVERY_DENOISE = 0.30
DEFAULT_STYLE_RECOVERY_DENOISE = 0.35


def assert_img2img_workflow(
    name: str = STYLE_RECOVERY_WORKFLOW,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    """Validate workflow is genuine img2img (LoadImage → VAEEncode), not txt2img."""
    loaded = load_workflow(name, root=root)
    meta = loaded.get("_meta") or {}
    validation = validate_api_workflow(loaded["prompt"])
    mode = validation.get("mode")
    roles = validation.get("roles") or {}
    has_load = bool(roles.get("load_image"))
    has_vae = bool(roles.get("vae_encode"))
    has_size = bool(roles.get("size"))
    report = {
        "workflow": name,
        "workflow_id": meta.get("workflow_id"),
        "mode": mode,
        "LoadImage": has_load,
        "VAEEncode": has_vae,
        "EmptyLatentImage": has_size,
        "IMAGE_TO_IMAGE": mode == "img2img" and has_load and has_vae and not has_size,
        "conditioning_method": meta.get("conditioning_method"),
        "default_denoise": (meta.get("default_settings") or {}).get("denoise"),
        "validation_ok": validation.get("ok"),
        "missing_roles": validation.get("missing_roles"),
    }
    if mode != "img2img" or not report["IMAGE_TO_IMAGE"]:
        raise RuntimeError(
            "TXT2IMG_FALLBACK_DISABLED: style recovery requires genuine img2img workflow "
            f"(LoadImage→VAEEncode). Got mode={mode} LoadImage={has_load} "
            f"VAEEncode={has_vae} EmptyLatentImage={has_size}. "
            f"Use {STYLE_RECOVERY_WORKFLOW}, NOT style-master-toonyou-beta6.json."
        )
    if meta.get("conditioning_method") != "IMAGE_TO_IMAGE":
        raise RuntimeError(
            f"Workflow meta conditioning_method must be IMAGE_TO_IMAGE, got {meta.get('conditioning_method')}"
        )
    denoise = float((meta.get("default_settings") or {}).get("denoise") or 1.0)
    if denoise >= 1.0:
        raise RuntimeError(
            f"Style recovery denoise must be < 1.0 (got default {denoise}) — denoise=1.0 destroys reference influence"
        )
    if not (MIN_STYLE_RECOVERY_DENOISE <= denoise <= MAX_STYLE_RECOVERY_DENOISE):
        # warn via report but allow if still < 1.0 — operator may override per candidate
        report["denoise_band_warning"] = (
            f"default denoise {denoise} outside preferred band "
            f"{MIN_STYLE_RECOVERY_DENOISE}–{MAX_STYLE_RECOVERY_DENOISE}"
        )
    report["ok"] = True
    return report


def assert_queued_graph_is_img2img(prompt: dict[str, Any], *, denoise: float) -> None:
    """Inspect the API prompt about to be queued — refuse txt2img / denoise=1.0."""
    if denoise >= 1.0:
        raise RuntimeError(
            f"TXT2IMG_FALLBACK_DISABLED: denoise={denoise} ≥ 1.0 destroys reference influence"
        )
    if denoise < MIN_STYLE_RECOVERY_DENOISE or denoise > MAX_STYLE_RECOVERY_DENOISE:
        raise RuntimeError(
            f"Style recovery denoise {denoise} outside allowed band "
            f"{MIN_STYLE_RECOVERY_DENOISE}–{MAX_STYLE_RECOVERY_DENOISE}"
        )
    class_types = {
        nid: (node.get("class_type") or "")
        for nid, node in prompt.items()
        if isinstance(node, dict)
    }
    if "EmptyLatentImage" in class_types.values():
        raise RuntimeError(
            "TXT2IMG_FALLBACK_DISABLED: EmptyLatentImage present — refusing txt2img path"
        )
    if "LoadImage" not in class_types.values():
        raise RuntimeError("TXT2IMG_FALLBACK_DISABLED: LoadImage node missing from queued graph")
    if "VAEEncode" not in class_types.values():
        raise RuntimeError("TXT2IMG_FALLBACK_DISABLED: VAEEncode node missing from queued graph")
    load_ok = False
    for node in prompt.values():
        if not isinstance(node, dict) or node.get("class_type") != "LoadImage":
            continue
        image = (node.get("inputs") or {}).get("image")
        if not image or image in {"", "capos_reference.png", "POSITIVE"}:
            raise RuntimeError(
                f"LoadImage has no uploaded reference filename (got {image!r}) — "
                "reference must be supplied to LoadImage, not converted to prompt text"
            )
        load_ok = True
    if not load_ok:
        raise RuntimeError("LoadImage node not found or not injected")
    for node in prompt.values():
        if not isinstance(node, dict) or node.get("class_type") != "KSampler":
            continue
        d = float((node.get("inputs") or {}).get("denoise", 1.0))
        if d >= 1.0:
            raise RuntimeError(f"KSampler denoise={d} ≥ 1.0 — refusing")
        latent = (node.get("inputs") or {}).get("latent_image")
        if not latent:
            raise RuntimeError("KSampler missing latent_image link from VAEEncode")


def comfyui_style_recovery_healthcheck(
    *,
    reference_path: str | Path | None = None,
    checkpoint: str | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """Full pre-generation gate for Phase 2B. Fail closed with exact remediation."""
    report: dict[str, Any] = {
        "ok": False,
        "comfyui_connection": "BLOCKED",
        "checkpoint": checkpoint or os.environ.get("CAPOS_COMFYUI_CHECKPOINT"),
        "workflow": STYLE_RECOVERY_WORKFLOW,
        "workflow_mode": None,
        "txt2img_fallback": "DISABLED",
        "mock_fallback": "DISABLED",
        "remediation": None,
        "checks": {},
    }
    base_url = (os.environ.get("CAPOS_COMFYUI_URL") or "").rstrip("/")
    if not base_url:
        report["remediation"] = "Set CAPOS_COMFYUI_URL=http://127.0.0.1:8188"
        return report

    client = ComfyUIClient(base_url)
    health = client.health()
    report["checks"]["connection"] = health
    if not health.get("ok"):
        report["remediation"] = (
            f"Start ComfyUI and confirm it answers at {base_url} "
            f"(reason: {health.get('reason')})"
        )
        return report
    report["comfyui_connection"] = "CONNECTED"

    ckpt = report["checkpoint"] or "toonyou_beta6.safetensors"
    report["checkpoint"] = ckpt
    present, present_reason = client.checkpoint_present(ckpt)
    report["checks"]["checkpoint"] = {"ok": present, "reason": present_reason, "name": ckpt}
    if not present:
        # Soft-fail: some ComfyUI builds lack listing API — still warn with remediation
        report["checks"]["checkpoint"]["warning"] = (
            "Could not confirm checkpoint via API — verify models/checkpoints/ manually"
        )
        if "not found" in present_reason.lower():
            report["remediation"] = (
                f"Place {ckpt} in ComfyUI models/checkpoints/ and restart ComfyUI"
            )
            report["comfyui_connection"] = "CONNECTED"
            report["ok"] = False
            return report

    try:
        object_info = client.get_object_info()
        available_types = set(object_info.keys()) if isinstance(object_info, dict) else set()
        missing_nodes = [t for t in REQUIRED_NODE_TYPES if t not in available_types]
        report["checks"]["nodes"] = {
            "ok": not missing_nodes or not available_types,
            "missing": missing_nodes,
            "listed_count": len(available_types),
        }
        if available_types and missing_nodes:
            report["remediation"] = (
                f"ComfyUI missing required nodes: {missing_nodes}. "
                "Update ComfyUI core — these are built-in SD1.5 nodes."
            )
            return report
    except Exception as exc:  # noqa: BLE001
        report["checks"]["nodes"] = {
            "ok": True,
            "warning": f"object_info unavailable ({exc}) — continuing with workflow file validation",
        }

    configured, cfg_reason = workflow_is_configured(STYLE_RECOVERY_WORKFLOW, root=root)
    report["checks"]["workflow_configured"] = {"ok": configured, "reason": cfg_reason}
    if not configured:
        report["remediation"] = cfg_reason
        return report

    try:
        img2img = assert_img2img_workflow(STYLE_RECOVERY_WORKFLOW, root=root)
        report["checks"]["img2img"] = img2img
        report["workflow_mode"] = "IMG2IMG"
        report["workflow_id"] = img2img.get("workflow_id")
    except RuntimeError as exc:
        report["checks"]["img2img"] = {"ok": False, "error": str(exc)}
        report["workflow_mode"] = "INVALID"
        report["remediation"] = str(exc)
        return report

    # Describe style-master for operator clarity — must NOT be used for recovery
    try:
        master = describe_workflow("style-master-toonyou-beta6.json", root=root)
        report["checks"]["style_master_is_txt2img"] = {
            "mode": (master.get("validation") or {}).get("mode"),
            "note": "style-master-toonyou-beta6.json is txt2img — Phase 2B must NOT use it",
        }
    except Exception:  # noqa: BLE001
        pass

    if reference_path:
        ref = Path(reference_path)
        report["checks"]["reference_file"] = {
            "path": str(ref),
            "exists": ref.is_file(),
        }
        if not ref.is_file():
            report["remediation"] = f"Reference file missing: {ref}"
            return report
        try:
            uploaded = client.upload_image(ref, subfolder="capos_healthcheck")
            report["checks"]["reference_upload"] = {
                "ok": True,
                "name": uploaded.get("name"),
                "subfolder": uploaded.get("subfolder"),
            }
        except Exception as exc:  # noqa: BLE001
            report["checks"]["reference_upload"] = {"ok": False, "error": str(exc)}
            report["remediation"] = (
                f"ComfyUI /upload/image failed: {exc}. "
                "Ensure ComfyUI accepts image uploads."
            )
            return report

    report["ok"] = True
    report["remediation"] = None
    return report


def select_target_reference(
    refs: list[Any],
    *,
    target: str = "likkle-jay",
) -> Any:
    """Pick one approved reference for the recovery target — do not blend all refs."""
    preferences = {
        "likkle-jay": (
            "character-likkle-jay-v1",
            "likkle-jay",
            "jay",
        ),
        "auntie-bev": (
            "character-auntie-bev-v1",
            "auntie-bev",
            "auntie",
        ),
        "kitchen": (
            "location-kitchen-v1",
            "kitchen",
        ),
        "cookie-jar": (
            "prop-cookie-jar-v1",
            "cookie",
        ),
    }
    keys = preferences.get(target, preferences["likkle-jay"])

    def _blob(ref: Any) -> str:
        rid = getattr(ref, "reference_id", "") or ""
        file = getattr(ref, "file", "") or ""
        notes = getattr(ref, "notes", "") or ""
        return f"{rid} {file} {notes}".lower()

    for key in keys:
        for ref in refs:
            if key.lower() in _blob(ref):
                return ref
    if not refs:
        raise RuntimeError(f"No references available for target={target}")
    return refs[0]
