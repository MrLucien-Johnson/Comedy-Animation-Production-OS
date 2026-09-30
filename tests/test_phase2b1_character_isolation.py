"""Phase 2B.1 — character isolation derived crop + hold."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from capos.canon.candidates import CandidateAsset, CandidateBatch, CandidateStore
from capos.canon.diff import compare_character_isolation
from capos.canon.pipeline import CanonCreationPipeline
from capos.canon.style_recovery_hold import mark_style_recovery_technical_success
from capos.core.errors import ValidationError
from capos.core.status import CanonStatus, CanonStep, VisualReferenceType
from capos.references.derived_crop import (
    CropBox,
    character_isolation_gate,
    create_derived_character_crop,
)
from capos.references.ingestion import VisualReferenceStore


def _png(path: Path, size=(400, 600), color=(180, 120, 70)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)
    return path


def test_mark_style_recovery_technical_success(tmp_project):
    store = CandidateStore("likkle-jay", root=tmp_project)
    img = _png(tmp_project / "r1.png")
    store.upsert(
        CandidateBatch(
            batch_id="style-recovery-batch-001",
            series_id="likkle-jay",
            step=CanonStep.STYLE_RECOVERY,
            target_asset_id="style-likkle-jay-v1",
            status=CanonStatus.AWAITING_HUMAN_STYLE_RECOVERY_REVIEW,
            candidates=[
                CandidateAsset(
                    candidate_id="style-recovery-candidate-001",
                    file=str(img),
                    status=CanonStatus.CANDIDATE,
                    batch_kind="style_recovery",
                )
            ],
        )
    )
    result = mark_style_recovery_technical_success("likkle-jay", root=tmp_project)
    assert result["ok"] is True
    batch = store.get("style-recovery-batch-001")
    assert batch is not None
    assert batch.status == CanonStatus.TECHNICAL_SUCCESS_STYLE_RECOVERY_NOT_YET_APPROVED
    assert batch.candidates[0].qa_summary.get("do_not_select_as_canon") is True
    assert Path(batch.candidates[0].file).is_file()
    with pytest.raises(ValidationError, match="do_not_select|technical-success|canon"):
        store.select_candidate("style-recovery-batch-001", "style-recovery-candidate-001")


def test_derived_crop_preserves_original(tmp_project):
    store = VisualReferenceStore("likkle-jay", root=tmp_project)
    src = _png(tmp_project / "character-likkle-jay-v1.png", size=(500, 700), color=(160, 100, 50))
    original_bytes = src.read_bytes()
    ref = store.import_reference(
        src,
        reference_type=VisualReferenceType.STYLE_REFERENCE,
        reference_id="character-likkle-jay-v1",
    )
    store.approve_reference(ref.reference_id)
    derived = create_derived_character_crop(
        store,
        source_reference_id="character-likkle-jay-v1",
        crop=CropBox(50, 40, 250, 540),
        derived_id="character-likkle-jay-front-derived-v1",
    )
    assert derived.reference_type == VisualReferenceType.DERIVED_CHARACTER_REFERENCE
    assert derived.status == CanonStatus.CANDIDATE
    assert Path(derived.file).is_file()
    assert Path(ref.file).read_bytes() == original_bytes  # untouched
    assert derived.provenance["source_reference_id"] == "character-likkle-jay-v1"
    assert derived.provenance["source_sha256"] == ref.checksum
    assert derived.provenance["crop"]["left"] == 50
    assert derived.provenance["original_untouched"] is True
    with pytest.raises(ValidationError, match="never overwrite|already exists"):
        create_derived_character_crop(
            store,
            source_reference_id="character-likkle-jay-v1",
            crop=CropBox(10, 10, 100, 200),
            derived_id="character-likkle-jay-front-derived-v1",
        )


def test_character_isolation_gate(tmp_project):
    store = VisualReferenceStore("likkle-jay", root=tmp_project)
    gate0 = character_isolation_gate(store)
    assert gate0["ready"] is False
    assert gate0["stop"] == "AWAITING_DERIVED_REFERENCE_APPROVAL"
    src = _png(tmp_project / "character-likkle-jay-v1.png")
    ref = store.import_reference(
        src,
        reference_type=VisualReferenceType.CHARACTER_REFERENCE,
        reference_id="character-likkle-jay-v1",
    )
    store.approve_reference(ref.reference_id)
    derived = create_derived_character_crop(
        store,
        source_reference_id="character-likkle-jay-v1",
        crop=CropBox(20, 20, 200, 400),
    )
    gate1 = character_isolation_gate(store)
    assert gate1["ready"] is False
    assert gate1["derived_reference_approved"] is False
    store.approve_reference(derived.reference_id)
    gate2 = character_isolation_gate(store)
    assert gate2["ready"] is True
    assert gate2["derived_reference_approved"] is True


def test_isolation_generation_blocked_without_derived(tmp_project):
    pipe = CanonCreationPipeline("likkle-jay", root=tmp_project)
    batch = pipe.generate_character_isolation_candidates()
    assert batch.status == CanonStatus.AWAITING_DERIVED_REFERENCE_APPROVAL
    assert batch.candidates == []


def test_compare_character_isolation_structure(tmp_project):
    report = compare_character_isolation(series_id="likkle-jay", root=tmp_project)
    assert report["identity_claim"] is False
    assert report["semantic_identity_score"] is None
    assert "FACE_IDENTITY" in report["human_review_categories"]
    assert "HAIR" in report["human_review_categories"]
