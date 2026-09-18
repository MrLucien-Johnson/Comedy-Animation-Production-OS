"""ComfyUI backend — optional remote API; never pretend availability."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from capos.generation.backend import GenerationBackend, GenerationResult


class ComfyUIBackend(GenerationBackend):
    name = "comfyui"

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or os.environ.get("CAPOS_COMFYUI_URL") or "").rstrip("/")

    def available(self) -> tuple[bool, str]:
        if not self.base_url:
            return False, "CAPOS_COMFYUI_URL not set"
        try:
            with urlopen(f"{self.base_url}/system_stats", timeout=3) as resp:
                if resp.status == 200:
                    return True, f"ComfyUI reachable at {self.base_url}"
                return False, f"ComfyUI HTTP {resp.status}"
        except URLError as exc:
            return False, f"ComfyUI unreachable: {exc}"
        except Exception as exc:  # noqa: BLE001
            return False, f"ComfyUI check failed: {exc}"

    def supports_reference_images(self) -> bool:
        return True

    def supports_edit(self) -> bool:
        return True

    def supports_inpaint(self) -> bool:
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
        ok, reason = self.available()
        if not ok:
            return GenerationResult(success=False, backend=self.name, error=reason)
        # Workflow execution is environment-specific; do not fabricate outputs.
        return GenerationResult(
            success=False,
            backend=self.name,
            error=(
                "ComfyUI is reachable but no CAPOS workflow template is configured. "
                "Set CAPOS_COMFYUI_WORKFLOW_PATH to enable production generation."
            ),
        )
