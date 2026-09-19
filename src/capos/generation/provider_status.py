"""Honest provider availability for the production dashboard."""

from __future__ import annotations

import os
from typing import Any

from capos.core.status import ProviderAvailability
from capos.generation.registry import list_backends, try_register_optional_backends
from capos.hardware.profile import detect_gpu, load_hardware_profile, resolve_generation_settings


def classify_backend(name: str, health: dict[str, Any]) -> ProviderAvailability:
    available = bool(health.get("available"))
    reason = str(health.get("reason", "")).lower()
    if name == "mock":
        return ProviderAvailability.AVAILABLE if available else ProviderAvailability.UNAVAILABLE
    if name == "null":
        return ProviderAvailability.UNAVAILABLE
    if name == "huggingface":
        if "not set" in reason or "token" in reason and not available:
            return ProviderAvailability.NOT_CONFIGURED
        if not available:
            return ProviderAvailability.UNAVAILABLE
        return ProviderAvailability.AVAILABLE
    if name == "local":
        if "not installed" in reason or "not found" in reason:
            return ProviderAvailability.NOT_CONFIGURED
        if not available:
            return ProviderAvailability.UNAVAILABLE
        return ProviderAvailability.AVAILABLE
    if name == "comfyui":
        if "not set" in reason:
            return ProviderAvailability.NOT_CONFIGURED
        if not available:
            return ProviderAvailability.UNAVAILABLE
        return ProviderAvailability.AVAILABLE
    if not available:
        if "config" in reason or "token" in reason or "not set" in reason:
            return ProviderAvailability.NOT_CONFIGURED
        return ProviderAvailability.UNAVAILABLE
    return ProviderAvailability.AVAILABLE


def comfyui_dashboard_panel() -> dict[str, Any]:
    """Rich ComfyUI + hardware panel for Providers UI (no secrets)."""
    from capos.generation.comfyui.workflows import (
        describe_workflow,
        list_workflows,
        workflow_is_configured,
    )
    from capos.generation.comfyui_backend import ComfyUIBackend
    from capos.generation.model_licence import environment_runtime_status, load_model_provenance

    hw = load_hardware_profile()
    gen = resolve_generation_settings(hw)
    gpu = detect_gpu()
    backend = ComfyUIBackend()
    ok, reason = backend.available()
    availability = classify_backend("comfyui", {"available": ok, "reason": reason})
    workflow = os.environ.get("CAPOS_COMFYUI_WORKFLOW", "style-master-toonyou-beta6.json")
    wf_ok, wf_reason = workflow_is_configured(workflow)
    checkpoint = os.environ.get("CAPOS_COMFYUI_CHECKPOINT", "toonyou_beta6.safetensors")
    prov = load_model_provenance()
    runtime = environment_runtime_status()
    model_ready = bool(os.environ.get("CAPOS_COMFYUI_CHECKPOINT")) and wf_ok and ok
    local_status = runtime["local_provider_status"]
    if ok and model_ready:
        local_status = "LOCAL_RUNTIME_VERIFIED"
    elif not ok:
        local_status = "LOCAL_EXECUTION_REQUIRED"
    try:
        wf_desc = describe_workflow(workflow)
    except Exception as exc:  # noqa: BLE001
        wf_desc = {"error": str(exc)}
    return {
        "label": "COMFYUI LOCAL",
        "status": availability.value,
        "local_provider": local_status,
        "runtime": runtime,
        "url_configured": bool(backend.base_url),
        "url_host": backend.base_url or None,
        "gpu": {
            "detected": gpu.get("detected"),
            "name": gpu.get("name") or hw.gpu_name_hint,
            "vram_mb": gpu.get("vram_mb"),
            "source": gpu.get("source"),
            "error": gpu.get("error"),
        },
        "vram_class": hw.vram_class,
        "profile_id": hw.profile_id,
        "generation_profile": hw.generation_profile,
        "resolution": f"{gen['width']}x{gen['height']}",
        "concurrency": gen["concurrency"],
        "model": checkpoint if os.environ.get("CAPOS_COMFYUI_CHECKPOINT") else None,
        "model_default": "toonyou_beta6.safetensors",
        "model_licence": prov.get("licence"),
        "model_licence_status": prov.get("licence_status"),
        "commercial_use": prov.get("commercial_use"),
        "workflow": workflow,
        "workflow_configured": wf_ok,
        "workflow_reason": wf_reason,
        "workflow_describe": wf_desc,
        "workflows_on_disk": list_workflows(),
        "capabilities": backend.health_check().get("capabilities"),
        "production_eligible": bool(ok and model_ready),
        "reason": reason,
        "connection_ok": ok,
        "operator_manual_note": runtime["production_machine"]["operator_manual_verification"],
    }


def provider_dashboard_status() -> list[dict[str, Any]]:
    try_register_optional_backends()
    from capos.generation.registry import _REGISTRY

    rows: list[dict[str, Any]] = []
    for name in list_backends():
        backend = _REGISTRY[name]()
        health = backend.health_check()
        availability = classify_backend(name, health)
        rows.append(
            {
                "name": name,
                "availability": availability.value,
                "available_raw": health.get("available"),
                "reason": health.get("reason"),
                "supports_edit": health.get("supports_edit"),
                "supports_reference_images": health.get("supports_reference_images"),
                "supports_inpaint": health.get("supports_inpaint"),
                "model": health.get("model"),
                "prefer_reference_edit": True,
            }
        )
    # Ensure local appears even if not registered
    names = {r["name"] for r in rows}
    if "local" not in names:
        rows.append(
            {
                "name": "local",
                "availability": ProviderAvailability.NOT_CONFIGURED.value,
                "available_raw": False,
                "reason": "Local diffusion backend not registered/configured",
                "supports_edit": False,
                "supports_reference_images": False,
                "supports_inpaint": False,
                "model": None,
                "prefer_reference_edit": True,
            }
        )
    if "huggingface" not in names:
        token = bool(os.environ.get("HF_TOKEN"))
        rows.append(
            {
                "name": "huggingface",
                "availability": (
                    ProviderAvailability.NOT_CONFIGURED.value
                    if not token
                    else ProviderAvailability.UNAVAILABLE.value
                ),
                "available_raw": False,
                "reason": "HF_TOKEN not set" if not token else "huggingface backend not importable",
                "supports_edit": False,
                "supports_reference_images": False,
                "supports_inpaint": False,
                "model": None,
                "prefer_reference_edit": True,
            }
        )
    if "comfyui" not in names:
        rows.append(
            {
                "name": "comfyui",
                "availability": (
                    ProviderAvailability.NOT_CONFIGURED.value
                    if not os.environ.get("CAPOS_COMFYUI_URL")
                    else ProviderAvailability.UNAVAILABLE.value
                ),
                "available_raw": False,
                "reason": "CAPOS_COMFYUI_URL not set"
                if not os.environ.get("CAPOS_COMFYUI_URL")
                else "comfyui backend not importable",
                "supports_edit": True,
                "supports_reference_images": True,
                "supports_inpaint": False,
                "model": None,
                "prefer_reference_edit": True,
            }
        )
    return sorted(rows, key=lambda r: r["name"])


def prefer_edit_over_regen(capabilities: dict[str, Any]) -> bool:
    return bool(capabilities.get("supports_edit") or capabilities.get("supports_inpaint"))
