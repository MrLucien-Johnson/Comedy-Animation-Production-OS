"""Honest null backend — always unavailable."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from capos.generation.backend import GenerationBackend, GenerationResult


class NullBackend(GenerationBackend):
    name = "null"

    def available(self) -> tuple[bool, str]:
        return False, "Null backend is intentionally unavailable"

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
        return GenerationResult(
            success=False,
            backend=self.name,
            error="Null backend cannot generate images",
        )
