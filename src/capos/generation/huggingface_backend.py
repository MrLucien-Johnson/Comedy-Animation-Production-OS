"""Optional Hugging Face backend — only succeeds when token + hub available."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from capos.generation.backend import GenerationBackend, GenerationResult


class HuggingFaceBackend(GenerationBackend):
    name = "huggingface"

    def available(self) -> tuple[bool, str]:
        if not os.environ.get("HF_TOKEN"):
            return False, "HF_TOKEN not set"
        try:
            import huggingface_hub  # noqa: F401
        except ImportError:
            return False, "huggingface_hub not installed"
        return True, "HF_TOKEN present and huggingface_hub importable"

    def supports_reference_images(self) -> bool:
        return False

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
        if not ok:
            return GenerationResult(success=False, backend=self.name, error=reason)

        try:
            from huggingface_hub import InferenceClient
        except ImportError as exc:
            return GenerationResult(success=False, backend=self.name, error=str(exc))

        settings = settings or {}
        model = settings.get("model") or "black-forest-labs/FLUX.1-schnell"
        out = Path(output_path) if output_path else Path("hf_out.png")
        out.parent.mkdir(parents=True, exist_ok=True)

        try:
            client = InferenceClient(token=os.environ["HF_TOKEN"])
            image = client.text_to_image(prompt, model=model)
            image.save(out)
        except Exception as exc:  # noqa: BLE001 — record refusal/errors honestly
            msg = str(exc)
            refusal = msg if "content" in msg.lower() or "policy" in msg.lower() else None
            return GenerationResult(
                success=False,
                backend=self.name,
                model=model,
                error=msg,
                refusal=refusal,
            )

        if not out.is_file():
            return GenerationResult(
                success=False,
                backend=self.name,
                model=model,
                error="HF call returned without creating an output file",
            )

        return GenerationResult(
            success=True,
            output_path=out,
            seed=seed,
            backend=self.name,
            model=model,
        )
