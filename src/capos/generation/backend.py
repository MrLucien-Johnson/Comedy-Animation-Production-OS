"""Generation backend abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GenerationResult:
    success: bool
    output_path: Path | None = None
    seed: int | None = None
    backend: str = ""
    model: str | None = None
    error: str | None = None
    refusal: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class GenerationBackend(ABC):
    """Provider-neutral image generation / edit interface."""

    name: str = "base"

    @abstractmethod
    def available(self) -> tuple[bool, str]:
        """Return (ok, reason). Never fabricate availability."""

    def health_check(self) -> dict[str, Any]:
        ok, reason = self.available()
        return {
            "backend": self.name,
            "available": ok,
            "reason": reason,
            "supports_seed": self.supports_seed(),
            "supports_negative_prompt": self.supports_negative_prompt(),
            "supports_reference_images": self.supports_reference_images(),
            "supports_edit": self.supports_edit(),
            "supports_inpaint": self.supports_inpaint(),
            "supports_outpaint": self.supports_outpaint(),
            "model": self.model_information(),
        }

    @abstractmethod
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
    ) -> GenerationResult: ...

    # Alias matching master prompt naming
    def generateImage(self, **kwargs: Any) -> GenerationResult:  # noqa: N802
        return self.generate_image(**kwargs)

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
        if not self.supports_edit():
            return GenerationResult(
                success=False,
                backend=self.name,
                error=f"Backend '{self.name}' does not support edit_image",
            )
        raise NotImplementedError

    def editImage(self, **kwargs: Any) -> GenerationResult:  # noqa: N802
        return self.edit_image(**kwargs)

    def generate_variation(
        self,
        *,
        source_image: str | Path,
        prompt: str = "",
        output_path: str | Path | None = None,
        settings: dict[str, Any] | None = None,
    ) -> GenerationResult:
        if not self.supports_edit():
            return GenerationResult(
                success=False,
                backend=self.name,
                error=f"Backend '{self.name}' does not support generate_variation",
            )
        raise NotImplementedError

    def generateVariation(self, **kwargs: Any) -> GenerationResult:  # noqa: N802
        return self.generate_variation(**kwargs)

    def reference_image(
        self,
        *,
        prompt: str,
        reference_images: list[str | Path],
        output_path: str | Path | None = None,
        settings: dict[str, Any] | None = None,
    ) -> GenerationResult:
        return self.generate_image(
            prompt=prompt,
            reference_images=reference_images,
            output_path=output_path,
            settings=settings,
        )

    def referenceImage(self, **kwargs: Any) -> GenerationResult:  # noqa: N802
        return self.reference_image(**kwargs)

    def inpaint(self, **kwargs: Any) -> GenerationResult:
        if not self.supports_inpaint():
            return GenerationResult(
                success=False,
                backend=self.name,
                error=f"Backend '{self.name}' does not support inpaint",
            )
        raise NotImplementedError

    def outpaint(self, **kwargs: Any) -> GenerationResult:
        if not self.supports_outpaint():
            return GenerationResult(
                success=False,
                backend=self.name,
                error=f"Backend '{self.name}' does not support outpaint",
            )
        raise NotImplementedError

    def supports_seed(self) -> bool:
        return True

    def supports_negative_prompt(self) -> bool:
        return True

    def supports_reference_images(self) -> bool:
        return False

    def supports_edit(self) -> bool:
        return False

    def supports_inpaint(self) -> bool:
        return False

    def supports_outpaint(self) -> bool:
        return False

    def model_information(self) -> dict[str, Any]:
        return {"name": None, "backend": self.name}
