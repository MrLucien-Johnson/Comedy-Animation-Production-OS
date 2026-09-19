"""Phase 2A — ComfyUI low-VRAM / RTX 3050 6GB activation tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from capos.canon.pipeline import CanonCreationPipeline
from capos.core.status import CanonStatus
from capos.generation.capabilities import select_production_provider
from capos.generation.comfyui.client import ComfyFailureKind, classify_comfy_error
from capos.generation.comfyui.workflows import (
    inject_basic_params,
    load_workflow,
    workflow_is_configured,
)
from capos.generation.comfyui_backend import ComfyUIBackend
from capos.generation.concurrency import generation_slot, lock_path
from capos.generation.image_validate import validate_candidate_image
from capos.generation.provider_status import comfyui_dashboard_panel, provider_dashboard_status
from capos.generation.telemetry import record_generation_telemetry, register_upscaled_derivative
from capos.hardware.profile import (
    GENERATION_PROFILES,
    HardwareProfile,
    assert_single_concurrency,
    load_hardware_profile,
    resolve_generation_settings,
)
from capos.pipeline.readiness import evaluate_season_production_ready


def _png(path: Path, size=(512, 512), color=(190, 120, 70)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)
    return path


def test_low_vram_6gb_profile_defaults(tmp_project):
    profile = load_hardware_profile(root=tmp_project)
    assert profile.profile_id == "LOW_VRAM_6GB"
    assert profile.vram_class == "LOW_6GB"
    assert profile.generation_concurrency == 1
    assert profile.allow_parallel_jobs is False
    assert profile.generation_profile == "SAFE"
    settings = resolve_generation_settings(profile)
    assert settings["concurrency"] == 1
    assert settings["width"] == 512
    assert settings["height"] == 512
    assert_single_concurrency(profile)


def test_generation_profiles_safe_default():
    assert "SAFE" in GENERATION_PROFILES
    assert GENERATION_PROFILES["QUALITY"].get("requires_smoke_ok") is True


def test_single_generation_concurrency_lock(tmp_project):
    with generation_slot(root=tmp_project, wait_s=2):
        assert lock_path(root=tmp_project).is_file()
        with pytest.raises(TimeoutError):
            with generation_slot(root=tmp_project, wait_s=0.3):
                pass
    assert not lock_path(root=tmp_project).is_file()


def test_comfyui_unavailable_without_url(monkeypatch):
    monkeypatch.delenv("CAPOS_COMFYUI_URL", raising=False)
    ok, reason = ComfyUIBackend().available()
    assert ok is False
    assert "not set" in reason.lower()


def test_comfyui_unavailable_when_unreachable(monkeypatch):
    monkeypatch.setenv("CAPOS_COMFYUI_URL", "http://127.0.0.1:9")
    ok, reason = ComfyUIBackend().available()
    assert ok is False
    assert reason


def test_cuda_oom_classification():
    assert classify_comfy_error("CUDA out of memory") == ComfyFailureKind.CUDA_OUT_OF_MEMORY
    assert classify_comfy_error("model load failed") == ComfyFailureKind.MODEL_LOAD_FAILURE
    assert classify_comfy_error("vae failed to load") == ComfyFailureKind.VAE_LOAD_FAILURE
    assert classify_comfy_error("timeout waiting") == ComfyFailureKind.TIMEOUT


def test_bounded_oom_retry_and_resolution_fallback(monkeypatch, tmp_project):
    monkeypatch.setenv("CAPOS_COMFYUI_URL", "http://127.0.0.1:8188")
    monkeypatch.setenv("CAPOS_COMFYUI_CHECKPOINT", "toy.safetensors")
    # Clear template_only via env workflow path with a configured copy
    src = Path(__file__).resolve().parents[1] / "workflows/comfyui/style-master-low-vram.json"
    data = json.loads(src.read_text())
    data["template_only"] = False
    wf_path = tmp_project / "wf.json"
    wf_path.write_text(json.dumps(data))
    monkeypatch.setenv("CAPOS_COMFYUI_WORKFLOW_PATH", str(wf_path))
    monkeypatch.setenv("CAPOS_COMFYUI_WORKFLOW", str(wf_path))

    calls: list[tuple[int, int]] = []

    def boom(**kwargs):
        w = kwargs["width"]
        h = kwargs["height"]
        calls.append((w, h))
        raise RuntimeError("CUDA out of memory")

    backend = ComfyUIBackend()
    with patch.object(backend, "available", return_value=(True, "ok")):
        with patch.object(backend, "_run_once", side_effect=boom):
            result = backend.generate_image(
                prompt="x",
                seed=42,
                settings={"force_width": 512, "force_height": 512, "workflow": str(wf_path)},
            )
    assert result.success is False
    assert result.metadata.get("failed_resource_limit") is True
    assert result.metadata.get("failure_kind") == ComfyFailureKind.CUDA_OUT_OF_MEMORY.value
    assert result.metadata.get("retry_count", 0) >= 1
    assert len(calls) >= 2  # bounded retries with smaller sizes
    assert calls[0][0] >= calls[-1][0]


def test_workflow_template_only_blocks(tmp_project):
    ok, reason = workflow_is_configured("style-master-low-vram.json", root=tmp_project)
    assert ok is False
    assert "template_only" in reason


def test_inject_basic_params_roles(tmp_project):
    loaded = load_workflow("smoke-test.json", root=tmp_project)
    wf = inject_basic_params(
        loaded["prompt"],
        positive="hello",
        negative="bad",
        seed=99,
        width=448,
        height=448,
        steps=10,
        cfg=6.5,
        checkpoint="a.safetensors",
    )
    texts = [n["inputs"].get("text") for n in wf.values() if "inputs" in n]
    assert "hello" in texts
    assert "bad" in texts
    sizes = [n["inputs"] for n in wf.values() if n.get("class_type") == "EmptyLatentImage"]
    assert sizes and sizes[0]["width"] == 448


def test_image_validate_square_checksum(tmp_project):
    p = _png(tmp_project / "ok.png")
    v = validate_candidate_image(p)
    assert v["ok"] is True
    assert v["square"] is True
    assert v["checksum"]
    bad = _png(tmp_project / "rect.png", size=(512, 256))
    v2 = validate_candidate_image(bad, require_square=True)
    assert v2["ok"] is False


def test_telemetry_and_upscale_provenance(tmp_project):
    path = record_generation_telemetry(
        {
            "backend": "comfyui",
            "model": "toy.safetensors",
            "workflow": "style-master-low-vram.json",
            "width": 512,
            "height": 512,
            "success": True,
            "oom": False,
            "retry_count": 0,
            "duration_ms": 12,
            "seed": 1001,
            "smoke_test": False,
            "secret_should_not_appear": "x",
        },
        root=tmp_project,
    )
    data = json.loads(path.read_text())
    assert "secret_should_not_appear" not in data
    assert data["success"] is True
    src = _png(tmp_project / "src.png")
    up = _png(tmp_project / "up.png", size=(1024, 1024))
    meta = register_upscaled_derivative(
        source_path=src, upscaled_path=up, series_id="likkle-jay", root=tmp_project
    )
    assert meta["kind"] == "UPSCALED_DERIVATIVE"
    assert meta["source_checksum"]
    assert Path(meta["upscaled_file"]).is_file()


def test_style_batch_blocked_no_mock_promotion(tmp_project, monkeypatch):
    monkeypatch.delenv("CAPOS_COMFYUI_URL", raising=False)
    pipe = CanonCreationPipeline("likkle-jay", root=tmp_project)
    batch = pipe.generate_style_candidates(count=3)
    assert batch.status == CanonStatus.BLOCKED_NO_PROVIDER
    assert not batch.candidates
    sel = select_production_provider()
    assert sel.get("production_eligible") is False
    assert sel.get("local_provider") in {"SETUP_REQUIRED", "LOCAL_EXECUTION_REQUIRED"}


def test_comfyui_panel_setup_required(monkeypatch):
    monkeypatch.delenv("CAPOS_COMFYUI_URL", raising=False)
    panel = comfyui_dashboard_panel()
    assert panel["label"] == "COMFYUI LOCAL"
    assert panel["local_provider"] in {"SETUP_REQUIRED", "LOCAL_EXECUTION_REQUIRED"}
    assert panel["vram_class"] == "LOW_6GB"
    rows = provider_dashboard_status()
    assert any(r["name"] == "comfyui" for r in rows)


def test_successful_generation_mocked(monkeypatch, tmp_project):
    monkeypatch.setenv("CAPOS_COMFYUI_URL", "http://127.0.0.1:8188")
    monkeypatch.setenv("CAPOS_COMFYUI_CHECKPOINT", "toy.safetensors")
    out = tmp_project / "gen.png"

    def fake_run_once(**kwargs):
        from capos.generation.backend import GenerationResult

        _png(Path(kwargs["output_path"]))
        return GenerationResult(
            success=True,
            output_path=Path(kwargs["output_path"]),
            seed=kwargs.get("seed"),
            backend="comfyui",
            model="toy.safetensors",
            metadata={
                "workflow": "style-master-low-vram.json",
                "width": 512,
                "height": 512,
                "duration_ms": 5,
                "generation_resolution": "512x512",
            },
        )

    backend = ComfyUIBackend()
    with patch.object(backend, "available", return_value=(True, "ok")):
        # bypass workflow_is_configured
        with patch(
            "capos.generation.comfyui_backend.workflow_is_configured",
            return_value=(True, "ok"),
        ):
            with patch.object(backend, "_run_once", side_effect=fake_run_once):
                result = backend.generate_image(
                    prompt="style",
                    seed=1001,
                    output_path=out,
                    settings={"force_width": 512, "force_height": 512},
                )
    assert result.success
    assert result.seed == 1001
    assert Path(result.output_path).is_file()
    v = validate_candidate_image(Path(result.output_path))
    assert v["ok"] and v["checksum"]


def test_smoke_test_excluded_from_canon_path(tmp_project, monkeypatch):
    from capos.generation.smoke import run_provider_smoke_test

    monkeypatch.delenv("CAPOS_COMFYUI_URL", raising=False)
    report = run_provider_smoke_test(root=tmp_project)
    assert report["ok"] is False
    assert report["canon"] is False
    assert report["tag"] == "PROVIDER_SMOKE_TEST"
    assert report["local_provider"] in {"SETUP_REQUIRED", "LOCAL_EXECUTION_REQUIRED"}


def test_mock_still_excluded_from_production():
    sel = select_production_provider()
    assert sel.get("name") != "mock"
    assert sel.get("production_eligible") is False


def test_readiness_engineering_yes_content_no(tmp_project):
    report = evaluate_season_production_ready("likkle-jay", root=tmp_project)
    assert report.engineering_ready is True
    assert report.season_production_ready is False


def test_hardware_profile_model():
    p = HardwareProfile(generation_profile="BALANCED")
    s = resolve_generation_settings(p)
    assert s["generation_profile"] == "BALANCED"
    assert s["concurrency"] == 1
