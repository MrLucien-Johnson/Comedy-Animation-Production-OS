"""Honest provider availability for the production dashboard."""

from __future__ import annotations

import os
from typing import Any

from capos.core.status import ProviderAvailability
from capos.generation.registry import list_backends, try_register_optional_backends


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
    return sorted(rows, key=lambda r: r["name"])


def prefer_edit_over_regen(capabilities: dict[str, Any]) -> bool:
    return bool(capabilities.get("supports_edit") or capabilities.get("supports_inpaint"))
