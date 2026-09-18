"""Provider capability matrix — honest reporting only."""

from __future__ import annotations

from typing import Any

from capos.core.status import ProviderAvailability, ProviderCapability
from capos.generation.provider_status import classify_backend
from capos.generation.registry import list_backends, try_register_optional_backends


def capabilities_for(backend_name: str, backend: Any) -> list[str]:
    caps: list[str] = []
    if getattr(backend, "supports_seed", lambda: False)():
        caps.append(ProviderCapability.SEED.value)
    if getattr(backend, "supports_negative_prompt", lambda: False)():
        caps.append(ProviderCapability.NEGATIVE_PROMPT.value)
    # TEXT_TO_IMAGE assumed if generate_image exists and backend is intended as generator
    if hasattr(backend, "generate_image"):
        caps.append(ProviderCapability.TEXT_TO_IMAGE.value)
    if getattr(backend, "supports_reference_images", lambda: False)():
        caps.append(ProviderCapability.REFERENCE_IMAGE.value)
    if getattr(backend, "supports_edit", lambda: False)():
        caps.append(ProviderCapability.IMAGE_TO_IMAGE.value)
    if getattr(backend, "supports_inpaint", lambda: False)():
        caps.append(ProviderCapability.INPAINT.value)
    if getattr(backend, "supports_outpaint", lambda: False)():
        caps.append(ProviderCapability.OUTPAINT.value)
    if getattr(backend, "supports_control_image", lambda: False)():
        caps.append(ProviderCapability.CONTROL_IMAGE.value)
    return caps


def capability_matrix() -> list[dict[str, Any]]:
    try_register_optional_backends()
    from capos.generation.registry import _REGISTRY

    rows = []
    for name in list_backends():
        backend = _REGISTRY[name]()
        health = backend.health_check()
        availability = classify_backend(name, health)
        caps = capabilities_for(name, backend)
        # Mock must never be treated as production-capable even if "available"
        production_eligible = availability == ProviderAvailability.AVAILABLE and name not in {
            "mock",
            "null",
        }
        rows.append(
            {
                "name": name,
                "availability": availability.value,
                "reason": health.get("reason"),
                "capabilities": caps,
                "production_eligible": production_eligible,
                "non_production": name == "mock",
                "prefer_reference_edit": ProviderCapability.IMAGE_TO_IMAGE.value in caps
                or ProviderCapability.INPAINT.value in caps,
            }
        )
    return sorted(rows, key=lambda r: r["name"])


def select_production_provider(preferred: str | None = None) -> dict[str, Any]:
    """Pick a real production-eligible provider. Prefer local ComfyUI. Never mock."""
    matrix = capability_matrix()
    eligible = [r for r in matrix if r["production_eligible"]]
    preferred = preferred or "comfyui"
    if preferred:
        for r in eligible:
            if r["name"] == preferred:
                return r
    # Prefer local routes over hosted inference when multiple are eligible
    for name in ("comfyui", "local", "huggingface"):
        for r in eligible:
            if r["name"] == name:
                return r
    if eligible:
        return eligible[0]
    return {
        "name": None,
        "availability": ProviderAvailability.NOT_CONFIGURED.value,
        "reason": "No production-eligible provider configured (mock is not production)",
        "capabilities": [],
        "production_eligible": False,
        "non_production": False,
        "blocker": (
            "Configure CAPOS_COMFYUI_URL for local ComfyUI (preferred on RTX 3050 6GB), "
            "or install local Diffusers / set HF_TOKEN. Mock art must not be used as canon."
        ),
        "local_provider": "SETUP_REQUIRED",
    }
