"""Backend registry with honest availability detection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from capos.core.config import get_config
from capos.generation.backend import GenerationBackend
from capos.generation.mock_backend import MockGenerationBackend

_REGISTRY: dict[str, type[GenerationBackend]] = {
    "mock": MockGenerationBackend,
}


def register_backend(name: str, cls: type[GenerationBackend]) -> None:
    _REGISTRY[name] = cls


def list_backends() -> list[str]:
    return sorted(_REGISTRY)


def get_backend(name: str | None = None) -> GenerationBackend:
    try_register_optional_backends()
    cfg = get_config()
    gen = cfg.get("generation", {})
    if gen.get("use_mock_backend", True):
        chosen = "mock"
    else:
        chosen = name or gen.get("preferred_production_provider") or gen.get(
            "default_backend", "comfyui"
        )
    if chosen not in _REGISTRY:
        if chosen == "mock":
            return MockGenerationBackend()
        # Do not silently substitute mock for a real provider request.
        raise RuntimeError(
            f"Backend '{chosen}' is not registered. "
            "Configure ComfyUI / local / HF, or set CAPOS_MOCK_GENERATION=1 for mock-only demos."
        )
    return _REGISTRY[chosen]()


def health_all() -> list[dict[str, Any]]:
    results = []
    for _name, cls in sorted(_REGISTRY.items()):
        backend = cls()
        results.append(backend.health_check())
    return results


def try_register_optional_backends() -> None:
    """Register optional backends if dependencies exist — never pretend they work."""
    try:
        from capos.generation.huggingface_backend import HuggingFaceBackend

        register_backend("huggingface", HuggingFaceBackend)
    except Exception:
        pass
    try:
        from capos.generation.null_backend import NullBackend

        register_backend("null", NullBackend)
    except Exception:
        pass
    try:
        from capos.generation.local_backend import LocalDiffusionBackend

        register_backend("local", LocalDiffusionBackend)
    except Exception:
        pass
    try:
        from capos.generation.comfyui_backend import ComfyUIBackend

        register_backend("comfyui", ComfyUIBackend)
    except Exception:
        pass


def record_provider_refusal(
    *,
    backend: str,
    prompt: str,
    refusal: str,
    log_dir: Path | None = None,
) -> Path:
    """Persist PROVIDER_REFUSED events — never claim success."""
    import json
    from datetime import UTC, datetime

    from capos.core.paths import project_root

    base = log_dir or (project_root() / "logs" / "provider_refusals")
    base.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = base / f"{stamp}_{backend}.json"
    path.write_text(
        json.dumps(
            {
                "status": "PROVIDER_REFUSED",
                "backend": backend,
                "refusal": refusal,
                "prompt_preview": prompt[:2000],
                "recorded_at": datetime.now(UTC).isoformat(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path
