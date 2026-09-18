"""Deterministic mock generation backend for CI and offline work."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from capos.generation.backend import GenerationBackend, GenerationResult


class MockGenerationBackend(GenerationBackend):
    name = "mock"

    def available(self) -> tuple[bool, str]:
        return True, "Mock backend always available (non-production art)"

    def supports_reference_images(self) -> bool:
        return True

    def supports_edit(self) -> bool:
        return True

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
        settings = settings or {}
        seed = 0 if seed is None else int(seed)
        out = Path(output_path) if output_path else Path(f"mock_{seed}.png")
        out.parent.mkdir(parents=True, exist_ok=True)

        # Warm cartoon-ish flat color — labeled non-production.
        img = Image.new("RGB", (width, height), (232, 168, 98))
        draw = ImageDraw.Draw(img)
        draw.rectangle([40, 40, width - 40, height - 40], outline=(40, 30, 20), width=6)
        label = "CAPOS MOCK — NOT PRODUCTION"
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
        draw.text((60, 60), label, fill=(40, 30, 20), font=font)
        draw.text((60, 100), f"seed={seed}", fill=(40, 30, 20), font=font)
        if reference_images:
            draw.text(
                (60, 140),
                f"refs={len(reference_images)}",
                fill=(40, 30, 20),
                font=font,
            )
        img.save(out)

        return GenerationResult(
            success=True,
            output_path=out,
            seed=seed,
            backend=self.name,
            model="capos-mock-v1",
            metadata={
                "non_production": True,
                "prompt_chars": len(prompt),
                "negative_chars": len(negative_prompt),
                "settings": settings,
            },
        )

    def edit_image(
        self,
        *,
        source_image: str | Path,
        prompt: str,
        negative_prompt: str = "",
        mask_path: str | Path | None = None,
        reference_images: list[str | Path] | None = None,
        output_path: str | Path | None = None,
        settings: dict[str, Any] | None = None,
    ) -> GenerationResult:
        src = Path(source_image)
        if not src.is_file():
            return GenerationResult(
                success=False, backend=self.name, error=f"Source missing: {src}"
            )
        out = Path(output_path) if output_path else src.with_name(src.stem + "_edit.png")
        img = Image.open(src).convert("RGB")
        draw = ImageDraw.Draw(img)
        draw.rectangle([10, 10, 200, 50], fill=(200, 60, 40))
        draw.text((16, 20), "MOCK EDIT", fill=(255, 255, 255))
        if mask_path:
            draw.text((16, 60), "masked", fill=(40, 30, 20))
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(out)
        return GenerationResult(
            success=True,
            output_path=out,
            backend=self.name,
            model="capos-mock-v1",
            metadata={"non_production": True, "edit": True, "prompt_chars": len(prompt)},
        )

    def generate_variation(
        self,
        *,
        source_image: str | Path,
        prompt: str = "",
        output_path: str | Path | None = None,
        settings: dict[str, Any] | None = None,
    ) -> GenerationResult:
        return self.edit_image(
            source_image=source_image,
            prompt=prompt or "variation",
            output_path=output_path,
            settings=settings,
        )
