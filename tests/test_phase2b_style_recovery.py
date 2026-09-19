"""Phase 2B — reference ingestion, style rejection, img2img recovery gates."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from capos.canon.candidates import CandidateAsset, CandidateBatch, CandidateStore
from capos.canon.diff import compare_to_reference
from capos.canon.pipeline import CanonCreationPipeline
from capos.canon.prompts import STYLE_RECOVERY_SEEDS
from capos.canon.style_rejection import (
    PHASE2A_BATCH_ID,
    REJECTION_CODE,
    reject_phase2a_style_drift,
)
from capos.core.errors import ValidationError
from capos.core.status import CanonStatus, CanonStep, VisualReferenceType
from capos.generation.comfyui.workflows import inject_basic_params, load_workflow, workflow_is_configured
from capos.generation.comfyui_backend import ComfyUIBackend
from capos.references.ingestion import VisualReferenceStore


def _png(path: Path, size=(512, 512), color=(200, 140, 80)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)
    return path


def test_reject_phase2a_style_drift_preserves_and_blocks_selection(tmp_project):
    store = CandidateStore("likkle-jay", root=tmp_project)
    img = _png(tmp_project / "c1.png")
    batch = CandidateBatch(
        batch_id=PHASE2A_BATCH_ID,
        series_id="likkle-jay",
        step=CanonStep.STYLE_MASTER,
        target_asset_id="style-likkle-jay-v1",
        status=CanonStatus.AWAITING_HUMAN_SELECTION,
        candidates=[
            CandidateAsset(
                candidate_id="style-master-candidate-001",
                file=str(img),
                status=CanonStatus.CANDIDATE,
                seed=305011,
            ),
            CandidateAsset(
                candidate_id="style-master-candidate-002",
                file=str(img),
                status=CanonStatus.CANDIDATE,
                seed=305022,
            ),
            CandidateAsset(
                candidate_id="style-master-candidate-003",
                file=str(img),
                status=CanonStatus.CANDIDATE,
                seed=305033,
            ),
        ],
    )
    store.upsert(batch)
    result = reject_phase2a_style_drift("likkle-jay", root=tmp_project)
    assert result["ok"] is True
    assert result["rejected_count"] == 3
    updated = store.get(PHASE2A_BATCH_ID)
    assert updated is not None
    assert updated.status == CanonStatus.HUMAN_REJECTED_STYLE_DRIFT
    for c in updated.candidates:
        assert c.status == CanonStatus.HUMAN_REJECTED_STYLE_DRIFT
        assert c.rejection_code == REJECTION_CODE
        assert c.qa_summary.get("do_not_select_as_canon") is True
        assert Path(c.file).is_file()  # preserved
    with pytest.raises(ValidationError, match="HUMAN_REJECTED_STYLE_DRIFT|do_not_select|style-drift"):
        store.select_candidate(PHASE2A_BATCH_ID, "style-master-candidate-001")


def test_visual_reference_import_never_overwrite(tmp_project):
    store = VisualReferenceStore("likkle-jay", root=tmp_project)
    src = _png(tmp_project / "ref_a.png", color=(180, 100, 60))
    ref = store.import_reference(
        src,
        reference_type=VisualReferenceType.STYLE_REFERENCE,
        reference_id="style-ref-001",
        notes="Likkle Jay kitchen sample",
    )
    assert ref.checksum
    assert Path(ref.file).is_file()
    with pytest.raises(ValidationError, match="never overwrite"):
        store.import_reference(
            src,
            reference_type=VisualReferenceType.STYLE_REFERENCE,
            reference_id="style-ref-001",
        )


def test_style_reference_set_gate_and_approve(tmp_project):
    store = VisualReferenceStore("likkle-jay", root=tmp_project)
    gate0 = store.style_recovery_gate()
    assert gate0["ready"] is False
    assert gate0["stop"] == "AWAITING_STYLE_REFERENCE_IMPORT"
    assert "visual_references" in gate0["import_folder"]

    ids = []
    for i in range(3):
        src = _png(tmp_project / f"sj_{i}.png", color=(160 + i * 10, 90, 50))
        ref = store.import_reference(
            src,
            reference_type=VisualReferenceType.STYLE_REFERENCE,
            reference_id=f"style-ref-{i:03d}",
        )
        store.approve_reference(ref.reference_id)
        ids.append(ref.reference_id)

    s = store.create_or_update_set(
        "likkle-jay-style-reference-set-v1",
        ids,
        notes="v1 curated",
    )
    assert s.status == CanonStatus.CANDIDATE
    approved = store.approve_set("likkle-jay-style-reference-set-v1")
    assert approved.status == CanonStatus.APPROVED
    with pytest.raises(ValidationError, match="APPROVED"):
        store.create_or_update_set("likkle-jay-style-reference-set-v1", ids)
    gate1 = store.style_recovery_gate()
    assert gate1["ready"] is True
    assert gate1["stop"] is None
    assert "likkle-jay-style-reference-set-v1" in gate1["approved_sets"]


def test_style_recovery_workflow_validates_as_img2img(tmp_project, monkeypatch):
    monkeypatch.setenv("CAPOS_COMFYUI_CHECKPOINT", "toonyou_beta6.safetensors")
    monkeypatch.delenv("CAPOS_COMFYUI_WORKFLOW_PATH", raising=False)
    loaded = load_workflow("style-recovery-img2img-low-vram.json", root=tmp_project)
    assert loaded["_meta"].get("conditioning_method") == "IMAGE_TO_IMAGE"
    ok, reason = workflow_is_configured("style-recovery-img2img-low-vram.json", root=tmp_project)
    assert ok is True, reason
    wf = inject_basic_params(
        loaded["prompt"],
        positive="warm cartoon",
        negative="anime",
        seed=405011,
        denoise=0.45,
        load_image_filename="capos/ref.png",
        checkpoint="toonyou_beta6.safetensors",
    )
    # LoadImage node should receive uploaded name
    load_nodes = [
        n for n in wf.values() if n.get("class_type") == "LoadImage" or "image" in (n.get("inputs") or {})
    ]
    assert any(
        (n.get("inputs") or {}).get("image") == "capos/ref.png"
        for n in wf.values()
        if isinstance(n, dict)
    )
    sampler = next(n for n in wf.values() if n.get("class_type") == "KSampler")
    assert sampler["inputs"]["denoise"] == 0.45
    assert sampler["inputs"]["seed"] == 405011


def test_next_actionable_step_awaits_style_import(tmp_project):
    reject_phase2a_style_drift("likkle-jay", root=tmp_project)
    pipe = CanonCreationPipeline("likkle-jay", root=tmp_project)
    nxt = pipe.next_actionable_step()
    assert nxt["stop"] == "AWAITING_STYLE_REFERENCE_IMPORT"
    assert nxt["step"] == CanonStep.STYLE_RECOVERY.value


def test_generate_style_recovery_stops_without_refs(tmp_project):
    pipe = CanonCreationPipeline("likkle-jay", root=tmp_project)
    batch = pipe.generate_style_recovery_candidates(count=3)
    assert batch.status == CanonStatus.AWAITING_STYLE_REFERENCE_IMPORT
    assert batch.candidates == []


def test_generate_style_recovery_with_mock_edit(tmp_project):
    store = VisualReferenceStore("likkle-jay", root=tmp_project)
    ids = []
    for i in range(3):
        src = _png(tmp_project / f"rec_{i}.png", color=(170, 110 + i * 5, 70))
        ref = store.import_reference(
            src,
            reference_type=VisualReferenceType.STYLE_REFERENCE,
            reference_id=f"rec-ref-{i}",
        )
        store.approve_reference(ref.reference_id)
        ids.append(ref.reference_id)
    store.create_or_update_set("likkle-jay-style-reference-set-v1", ids)
    store.approve_set("likkle-jay-style-reference-set-v1")

    from capos.generation import registry as reg
    from capos.generation.mock_backend import MockGenerationBackend

    with patch.object(
        CanonCreationPipeline,
        "can_generate_production",
        return_value=(True, "mock"),
    ), patch.dict(reg._REGISTRY, {"mock": MockGenerationBackend}, clear=False):
        pipe = CanonCreationPipeline("likkle-jay", root=tmp_project)
        batch = pipe.generate_style_recovery_candidates(count=3)

    assert batch.status == CanonStatus.AWAITING_HUMAN_STYLE_RECOVERY_REVIEW
    assert len(batch.candidates) == 3
    assert set(c.candidate_id for c in batch.candidates) == set(STYLE_RECOVERY_SEEDS)
    for c in batch.candidates:
        assert c.conditioning_method == "IMAGE_TO_IMAGE"
        assert c.reference_set_id == "likkle-jay-style-reference-set-v1"
        assert c.reference_ids
        assert c.reference_checksums
        assert c.denoise is not None
        assert Path(c.file).is_file()
        assert c.qa_summary.get("identity_claim") is False


def test_compare_to_reference_no_fake_score(tmp_project):
    store = VisualReferenceStore("likkle-jay", root=tmp_project)
    src = _png(tmp_project / "cref.png")
    ref = store.import_reference(
        src, reference_type=VisualReferenceType.STYLE_REFERENCE, reference_id="cmp-1"
    )
    store.approve_reference(ref.reference_id)
    cand = _png(tmp_project / "cand.png", color=(190, 120, 70))
    report = compare_to_reference(
        series_id="likkle-jay",
        candidate_file=cand,
        reference_id="cmp-1",
        root=tmp_project,
    )
    assert report["identity_claim"] is False
    assert report["semantic_identity_score"] is None
    assert report["review_required"] is True
    assert "LINEWORK_MATCH" in report["human_review_categories"]
    assert len(report["comparisons"]) == 1


def test_comfyui_edit_image_requires_seed(monkeypatch):
    monkeypatch.setenv("CAPOS_COMFYUI_URL", "http://127.0.0.1:8188")
    backend = ComfyUIBackend()
    result = backend.edit_image(
        source_image="/tmp/missing.png",
        prompt="x",
        settings={},  # no seed
    )
    assert result.success is False
    assert "seed" in (result.error or "").lower()
