"""Local diffusion backend stub — honest NOT_CONFIGURED / UNAVAILABLE."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from capos.generation.backend import GenerationBackend, GenerationResult


class LocalDiffusionBackend(GenerationBackend):
    name = "local"

    def available(self) -> tuple[bool, str]:
        try:
            import diffusers  # noqa: F401
            import torch  # noqa: F401
        except ImportError:
            return False, "Local diffusion dependencies not installed (torch/diffusers)"
        return False, "Local weights path not configured (no auto-download)"

    def generate_image(
        self,
        *,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        seed: int | None = None,
        reference_images: list[str | Path] | None = None,
        output_path: str | Path | None = None,
        settings: dict[str, Any] | None = None,
    ) -> GenerationResult:
        ok, reason = self.available()
        return GenerationResult(success=False, backend=self.name, error=reason)
