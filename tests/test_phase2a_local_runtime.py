"""Phase 2A continuation — local runtime verified / API workflow / licence."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from capos.canon.pipeline import CanonCreationPipeline
from capos.canon.prompts import STYLE_MASTER_SEEDS
from capos.core.errors import ValidationError
from capos.core.status import CanonStatus
from capos.generation.comfyui.validate import validate_api_workflow
from capos.generation.comfyui.workflows import inject_basic_params, load_workflow
from capos.generation.comfyui_backend import ComfyUIBackend
from capos.generation.model_licence import (
    environment_runtime_status,
    load_model_provenance,
    production_licence_gate,
)
from capos.generation.smoke import run_provider_smoke_test
from capos.pipeline.readiness import evaluate_season_production_ready


def _png(path: Path, size=(512, 512), color=(190, 120, 70)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)
    return path


def test_api_workflow_validation_toonyou(tmp_project):
    loaded = load_workflow("style-master-toonyou-beta6.json", root=tmp_project)
    report = validate_api_workflow(loaded["prompt"])
    assert report["ok"] is True
    assert report["configurable"]["checkpoint"] is True
    assert report["configurable"]["positive_prompt"] is True
    assert report["configurable"]["negative_prompt"] is True
    assert report["configurable"]["seed"] is True
    assert report["configurable"]["width"] is True
    assert report["configurable"]["output"] is True


def test_inject_checkpoint_prompt_seed_size(tmp_project):
    loaded = load_workflow("style-master-toonyou-beta6.json", root=tmp_project)
    wf = inject_basic_params(
        loaded["prompt"],
        positive="POS",
        negative="NEG",
        seed=305011,
        width=512,
        height=512,
        steps=20,
        cfg=7.0,
        checkpoint="toonyou_beta6.safetensors",
        sampler_name="euler",
        scheduler="normal",
        denoise=1.0,
    )
    texts = [n["inputs"].get("text") for n in wf.values() if "text" in n.get("inputs", {})]
    assert "POS" in texts and "NEG" in texts
    ckpts = [n["inputs"]["ckpt_name"] for n in wf.values() if "ckpt_name" in n.get("inputs", {})]
    assert ckpts == ["toonyou_beta6.safetensors"]
    sampler = next(n for n in wf.values() if n.get("class_type") == "KSampler")
    assert sampler["inputs"]["seed"] == 305011
    assert sampler["inputs"]["steps"] == 20
    assert sampler["inputs"]["cfg"] == 7.0
    assert sampler["inputs"]["sampler_name"] == "euler"
    assert sampler["inputs"]["scheduler"] == "normal"
    assert sampler["inputs"]["denoise"] == 1.0
    latent = next(n for n in wf.values() if n.get("class_type") == "EmptyLatentImage")
    assert latent["inputs"]["width"] == 512 and latent["inputs"]["height"] == 512


def test_raw_api_export_without_capos_roles(tmp_project):
    """ComfyUI Save (API Format) often lacks _meta.capos_role — heuristics must work."""
    raw = {
        "10": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "x.safetensors"},
        },
        "20": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "a", "clip": ["10", 1]},
        },
        "21": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "b", "clip": ["10", 1]},
        },
        "30": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 64, "height": 64, "batch_size": 1},
        },
        "40": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 1,
                "steps": 10,
                "cfg": 5,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["10", 0],
                "positive": ["20", 0],
                "negative": ["21", 0],
                "latent_image": ["30", 0],
            },
        },
        "50": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["40", 0], "vae": ["10", 2]},
        },
        "60": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "x", "images": ["50", 0]},
        },
    }
    assert validate_api_workflow(raw)["ok"] is True
    injected = inject_basic_params(raw, positive="P", negative="N", seed=99, width=512, height=512)
    assert injected["20"]["inputs"]["text"] == "P"
    assert injected["40"]["inputs"]["seed"] == 99


def test_toonyou_licence_unverified_fail_closed(tmp_project):
    prov = load_model_provenance(root=tmp_project)
    assert prov["model"] == "toonyou_beta6.safetensors"
    assert prov["licence_status"] == "UNVERIFIED"
    assert prov["commercial_use"] == "REQUIRES_AUTHOR_CONTACT"
    ok, reason = production_licence_gate(root=tmp_project)
    assert ok is False
    assert "UNVERIFIED" in reason or "Commercial" in reason
    report = evaluate_season_production_ready("likkle-jay", root=tmp_project)
    assert report.season_production_ready is False
    assert any(c.check_id == "MODEL_LICENCE" and c.status.value == "FAIL" for c in report.checks)


def test_cloud_local_execution_required(monkeypatch):
    monkeypatch.delenv("CAPOS_COMFYUI_URL", raising=False)
    runtime = environment_runtime_status()
    assert runtime["local_provider_status"] == "LOCAL_EXECUTION_REQUIRED"
    assert runtime["engineering_environment"]["has_comfyui_access"] is False
    assert "MANUALLY VERIFIED" in runtime["production_machine"]["operator_manual_verification"]


def test_style_seeds_are_deterministic():
    assert STYLE_MASTER_SEEDS["style-master-candidate-001"] == 305011
    assert STYLE_MASTER_SEEDS["style-master-candidate-002"] == 305022
    assert STYLE_MASTER_SEEDS["style-master-candidate-003"] == 305033
    assert len(set(STYLE_MASTER_SEEDS.values())) == 3


def test_comfyui_requires_explicit_seed(monkeypatch):
    monkeypatch.setenv("CAPOS_COMFYUI_URL", "http://127.0.0.1:8188")
    with patch.object(ComfyUIBackend, "available", return_value=(True, "ok")):
        r = ComfyUIBackend().generate_image(prompt="x", seed=None)
    assert r.success is False
    assert "seed" in (r.error or "").lower()


def test_same_seed_and_new_seed_methods_require_provider(tmp_project, monkeypatch):
    monkeypatch.delenv("CAPOS_COMFYUI_URL", raising=False)
    pipe = CanonCreationPipeline("likkle-jay", root=tmp_project)
    with pytest.raises(ValidationError):
        pipe.regenerate_style_same_seed("style-master-candidate-001")
    with pytest.raises(ValidationError):
        pipe.create_new_style_candidate(seed=999)


def test_smoke_reports_local_execution_required(tmp_project, monkeypatch):
    monkeypatch.delenv("CAPOS_COMFYUI_URL", raising=False)
    report = run_provider_smoke_test(root=tmp_project)
    assert report["ok"] is False
    assert report["local_provider"] == "LOCAL_EXECUTION_REQUIRED"


def test_mock_exclusion_unchanged(tmp_project):
    pipe = CanonCreationPipeline("likkle-jay", root=tmp_project)
    batch = pipe.generate_style_candidates(count=3)
    assert batch.status == CanonStatus.BLOCKED_NO_PROVIDER
    assert not batch.candidates
