"""ComfyUI generation backend — low-VRAM aware, no mock fallback."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from PIL import Image

from capos.generation.backend import GenerationBackend, GenerationResult
from capos.generation.comfyui.client import ComfyFailureKind, ComfyUIClient, classify_comfy_error
from capos.generation.comfyui.workflows import (
    inject_basic_params,
    load_workflow,
    workflow_is_configured,
)
from capos.generation.model_licence import load_model_provenance
from capos.generation.telemetry import record_generation_telemetry
from capos.hardware.profile import load_hardware_profile, resolve_generation_settings


class ComfyUIBackend(GenerationBackend):
    name = "comfyui"

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or os.environ.get("CAPOS_COMFYUI_URL") or "").rstrip("/")
        self._client: ComfyUIClient | None = None

    def client(self) -> ComfyUIClient:
        if not self.base_url:
            raise RuntimeError("CAPOS_COMFYUI_URL not set")
        if self._client is None:
            self._client = ComfyUIClient(self.base_url)
        return self._client

    def available(self) -> tuple[bool, str]:
        if not self.base_url:
            return False, "CAPOS_COMFYUI_URL not set"
        health = ComfyUIClient(self.base_url).health()
        return bool(health.get("ok")), str(health.get("reason"))

    def supports_reference_images(self) -> bool:
        return True

    def supports_edit(self) -> bool:
        ok, _ = workflow_is_configured("img2img-low-vram.json")
        ok2, _ = workflow_is_configured("controlled-edit-low-vram.json")
        return True if self.base_url else (ok or ok2)

    def supports_inpaint(self) -> bool:
        ok, _ = workflow_is_configured("inpaint-low-vram.json")
        return ok

    def supports_control_image(self) -> bool:
        ok, _ = workflow_is_configured("controlled-edit-low-vram.json")
        return ok

    def model_information(self) -> dict[str, Any]:
        prov = load_model_provenance()
        return {
            "name": os.environ.get("CAPOS_COMFYUI_CHECKPOINT") or prov.get("model"),
            "backend": self.name,
            "provider": "comfyui-local",
            "family": prov.get("family") or prov.get("architecture"),
            "licence_status": prov.get("licence_status"),
            "commercial_use": prov.get("commercial_use"),
            "licence_note": os.environ.get("CAPOS_COMFYUI_MODEL_LICENCE") or prov.get("licence"),
            "source": prov.get("source"),
        }

    def generate_image(
        self,
        *,
        prompt: str,
        negative_prompt: str = "",
        width: int = 512,
        height: int = 512,
        seed: int | None = None,
        reference_images: list[str | Path] | None = None,
        output_path: str | Path | None = None,
        settings: dict[str, Any] | None = None,
    ) -> GenerationResult:
        settings = dict(settings or {})
        if seed is None:
            return GenerationResult(
                success=False,
                backend=self.name,
                error="Explicit seed required — CAPOS does not use uncontrolled randomize",
                metadata={"failure_kind": ComfyFailureKind.CONFIG_MISSING.value},
            )
        ok, reason = self.available()
        if not ok:
            return GenerationResult(
                success=False,
                backend=self.name,
                error=reason,
                metadata={"failure_kind": ComfyFailureKind.UNAVAILABLE.value},
            )

        hw = resolve_generation_settings(load_hardware_profile())
        width = int(settings.get("force_width", hw["width"]))
        height = int(settings.get("force_height", hw["height"]))
        if hw.get("vram_class") == "LOW_6GB" and "force_width" not in settings:
            width = min(width, int(hw.get("width", 512)))
            height = min(height, int(hw.get("height", 512)))

        workflow_name = settings.get("workflow") or os.environ.get(
            "CAPOS_COMFYUI_WORKFLOW", "style-master-toonyou-beta6.json"
        )
        configured, cfg_reason = workflow_is_configured(workflow_name)
        if not configured:
            return GenerationResult(
                success=False,
                backend=self.name,
                error=cfg_reason,
                metadata={"failure_kind": ComfyFailureKind.CONFIG_MISSING.value},
            )

        retries = 0
        max_retries = int(hw.get("oom_max_retries", 2))
        fallbacks = list(hw.get("oom_fallback_widths") or [512, 448, 384])
        sizes = [(width, height)]
        for w in fallbacks:
            if (w, w) not in sizes and w < width:
                sizes.append((w, w))

        last_error = ""
        last_kind = ComfyFailureKind.UNKNOWN
        t0 = time.time()
        for _attempt, (w, h) in enumerate(sizes):
            try:
                return self._run_once(
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    width=w,
                    height=h,
                    seed=seed,
                    output_path=output_path,
                    workflow_name=workflow_name,
                    settings=settings,
                    retry_count=retries,
                    started=t0,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                last_kind = classify_comfy_error(last_error)
                retries += 1
                record_generation_telemetry(
                    {
                        "backend": self.name,
                        "workflow": workflow_name,
                        "width": w,
                        "height": h,
                        "success": False,
                        "failure_kind": last_kind.value,
                        "oom": last_kind == ComfyFailureKind.CUDA_OUT_OF_MEMORY,
                        "retry_count": retries,
                        "duration_ms": int((time.time() - t0) * 1000),
                        "profile": hw.get("generation_profile"),
                        "smoke_test": bool(settings.get("smoke_test")),
                    }
                )
                if last_kind != ComfyFailureKind.CUDA_OUT_OF_MEMORY:
                    break
                if retries > max_retries:
                    break

        return GenerationResult(
            success=False,
            backend=self.name,
            error=last_error or "ComfyUI generation failed",
            metadata={
                "failure_kind": (
                    ComfyFailureKind.CUDA_OUT_OF_MEMORY.value
                    if last_kind == ComfyFailureKind.CUDA_OUT_OF_MEMORY
                    else last_kind.value
                ),
                "failed_resource_limit": last_kind == ComfyFailureKind.CUDA_OUT_OF_MEMORY,
                "retry_count": retries,
            },
        )

    def _run_once(
        self,
        *,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        seed: int | None,
        output_path: str | Path | None,
        workflow_name: str,
        settings: dict[str, Any],
        retry_count: int,
        started: float,
    ) -> GenerationResult:
        loaded = load_workflow(workflow_name)
        meta_wf = loaded.get("_meta") or {}
        steps = int(settings.get("steps") or meta_wf.get("default_settings", {}).get("steps") or 20)
        cfg = float(settings.get("cfg") or meta_wf.get("default_settings", {}).get("cfg") or 7.0)
        sampler_name = settings.get("sampler_name") or meta_wf.get("default_settings", {}).get(
            "sampler_name", "euler"
        )
        scheduler = settings.get("scheduler") or meta_wf.get("default_settings", {}).get(
            "scheduler", "normal"
        )
        denoise = float(
            settings.get("denoise")
            if settings.get("denoise") is not None
            else meta_wf.get("default_settings", {}).get("denoise", 1.0)
        )
        checkpoint = os.environ.get("CAPOS_COMFYUI_CHECKPOINT") or meta_wf.get(
            "default_checkpoint", "toonyou_beta6.safetensors"
        )
        wf = inject_basic_params(
            loaded["prompt"],
            positive=prompt,
            negative=negative_prompt,
            seed=seed,
            width=width,
            height=height,
            steps=steps,
            cfg=cfg,
            checkpoint=checkpoint,
            sampler_name=sampler_name,
            scheduler=scheduler,
            denoise=denoise,
        )
        client = self.client()
        prompt_id = client.queue_prompt(wf)
        history = client.wait_for_completion(
            prompt_id, timeout_s=float(settings.get("timeout_s", 300))
        )
        raw, meta = client.first_image_from_history(history)
        out = Path(output_path) if output_path else Path(f"comfy_{prompt_id}.png")
        client.save_image_bytes(raw, out)
        with Image.open(out) as img:
            w, h = img.size
            if w < 1 or h < 1:
                raise RuntimeError(ComfyFailureKind.INVALID_OUTPUT.value)
        duration_ms = int((time.time() - started) * 1000)
        prov = load_model_provenance()
        record_generation_telemetry(
            {
                "backend": self.name,
                "model": checkpoint,
                "workflow": workflow_name,
                "width": w,
                "height": h,
                "resolution": f"{w}x{h}",
                "duration_ms": duration_ms,
                "success": True,
                "oom": False,
                "retry_count": retry_count,
                "seed": seed,
                "smoke_test": bool(settings.get("smoke_test")),
                "non_production": bool(settings.get("smoke_test")),
                "candidate_id": settings.get("candidate_id"),
                "batch_id": settings.get("batch_id"),
            }
        )
        return GenerationResult(
            success=True,
            output_path=out,
            seed=seed,
            backend=self.name,
            model=checkpoint,
            metadata={
                "provider": "comfyui-local",
                "workflow": workflow_name,
                "workflow_id": meta_wf.get("workflow_id"),
                "workflow_version": meta_wf.get("workflow_version"),
                "prompt_id": prompt_id,
                "comfy_image": meta,
                "width": w,
                "height": h,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler_name,
                "scheduler": scheduler,
                "denoise": denoise,
                "duration_ms": duration_ms,
                "smoke_test": bool(settings.get("smoke_test")),
                "generation_resolution": f"{w}x{h}",
                "positive_prompt": prompt,
                "negative_prompt": negative_prompt,
                "model_family": prov.get("architecture") or prov.get("family"),
                "model_licence_status": prov.get("licence_status"),
                "checkpoint": checkpoint,
            },
        )
