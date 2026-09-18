"""Phase 2 canon creation & approval tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from capos.canon.candidates import CandidateAsset, CandidateBatch, CandidateStore
from capos.canon.diff import compare_to_canon
from capos.canon.pipeline import CanonCreationPipeline, missing_parents
from capos.composition.masters import PROP_LABEL_COOKIES, WATERMARK
from capos.composition.prop_label import apply_cookies_label
from capos.core.errors import ValidationError
from capos.core.schemas import COOKIE_LABEL_EXACT, WATERMARK_EXACT, CanonicalAssetRef
from capos.core.status import CanonicalAssetType, CanonStatus, CanonStep
from capos.generation.capabilities import capability_matrix, select_production_provider
from capos.generation.null_backend import NullBackend
from capos.pipeline.readiness import evaluate_season_production_ready
from capos.production.storage import (
    ensure_production_tree,
    register_production_file,
    sha256_file,
)
from capos.references.golden import GoldenFrameStore
from capos.references.versioning import ReferenceStore


def _png(path: Path, color=(190, 120, 70)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (256, 256), color).save(path)
    return path


def test_production_storage_checksum(tmp_project):
    ensure_production_tree("likkle-jay", root=tmp_project)
    src = _png(tmp_project / "raw.png")
    meta = register_production_file(
        series_id="likkle-jay",
        category="style",
        asset_slug="style-master",
        source_path=src,
        root=tmp_project,
        kind="candidate",
    )
    assert Path(meta["file"]).is_file()
    assert meta["checksum"] == sha256_file(Path(meta["file"]))


def test_approval_refuses_without_image(tmp_project):
    store = ReferenceStore("likkle-jay", root=tmp_project)
    with pytest.raises(ValidationError):
        store.approve("style-likkle-jay-v1")


def test_candidate_to_approval_transition(tmp_project):
    store = ReferenceStore("likkle-jay", root=tmp_project)
    # ensure style asset exists
    if not store.get("style-likkle-jay-v1"):
        store.register(
            CanonicalAssetRef(
                asset_id="style-likkle-jay-v1",
                kind="style",
                type=CanonicalAssetType.STYLE_MASTER,
                series_id="likkle-jay",
                slug="likkle-jay",
                status=CanonStatus.DRAFT,
            )
        )
    img = _png(tmp_project / "style.png")
    store.attach_file("style-likkle-jay-v1", img)
    approved = store.approve("style-likkle-jay-v1")
    assert approved.status == CanonStatus.APPROVED
    locked = store.lock_as_canon("style-likkle-jay-v1")
    assert str(locked.status) == "LOCKED"


def test_immutable_approved_requires_v2(tmp_project):
    store = ReferenceStore("likkle-jay", root=tmp_project)
    img = _png(tmp_project / "c.png")
    store.attach_file("character-likkle-jay-v1", img)
    store.approve("character-likkle-jay-v1")
    with pytest.raises(ValidationError):
        store.attach_file("character-likkle-jay-v1", _png(tmp_project / "c2.png", (10, 10, 10)))
    v2 = store.create_new_version("character-likkle-jay-v1")
    assert v2.asset_id == "character-likkle-jay-v2"
    assert v2.supersedes == "character-likkle-jay-v1"


def test_dependency_inheritance_blocks_jay_without_style(tmp_project):
    pipe = CanonCreationPipeline("likkle-jay", root=tmp_project)
    missing = missing_parents(pipe.store, CanonStep.LIKKLE_JAY_MASTER)
    assert "style-likkle-jay-v1" in missing
    batch = pipe.generate_likkle_jay_candidates(count=3)
    assert batch.blocker
    assert "style-likkle-jay-v1" in batch.blocker


def test_style_batch_blocked_without_real_provider(tmp_project):
    pipe = CanonCreationPipeline("likkle-jay", root=tmp_project)
    batch = pipe.generate_style_candidates(count=3)
    assert batch.status == CanonStatus.BLOCKED_NO_PROVIDER
    assert not batch.candidates
    assert "mock" in (batch.blocker or "").lower() or "provider" in (batch.blocker or "").lower()


def test_human_selection_rejects_mock_candidate(tmp_project):
    store = CandidateStore("likkle-jay", root=tmp_project)
    img = _png(tmp_project / "mockcand.png")
    batch = CandidateBatch(
        batch_id="test-batch",
        series_id="likkle-jay",
        step=CanonStep.STYLE_MASTER,
        target_asset_id="style-likkle-jay-v1",
        status=CanonStatus.AWAITING_HUMAN_SELECTION,
        candidates=[
            CandidateAsset(
                candidate_id="c1",
                file=str(img),
                checksum="abc",
                non_production=True,
            )
        ],
    )
    store.upsert(batch)
    with pytest.raises(ValidationError):
        store.select_candidate("test-batch", "c1")


def test_cookies_and_watermark_compositing(tmp_project):
    src = _png(tmp_project / "jar.png")
    labeled = tmp_project / "jar_labeled.png"
    assert apply_cookies_label(src, labeled) == COOKIE_LABEL_EXACT
    assert PROP_LABEL_COOKIES.exact() == "COOKIES"
    with pytest.raises(AssertionError):
        apply_cookies_label(src, tmp_project / "bad.png", label="COOKIE")
    assert WATERMARK.apply(src, tmp_project / "wm.png") == WATERMARK_EXACT


def test_provider_capability_matrix_marks_mock_non_production():
    matrix = capability_matrix()
    by_name = {r["name"]: r for r in matrix}
    assert by_name["mock"]["production_eligible"] is False
    assert by_name["mock"]["non_production"] is True
    sel = select_production_provider()
    assert sel.get("production_eligible") is False
    assert sel.get("name") is None


def test_provider_generation_failure():
    r = NullBackend().generate_image(prompt="x")
    assert r.success is False


def test_golden_frame_resolution_still_reference_required(tmp_project):
    g = GoldenFrameStore("likkle-jay", root=tmp_project).ensure_s01e02_open_jar_placeholder()
    assert g.status == CanonStatus.REFERENCE_REQUIRED


def test_compare_to_canon(tmp_project):
    store = ReferenceStore("likkle-jay", root=tmp_project)
    img = _png(tmp_project / "parent.png")
    store.attach_file("prop-cookie-jar-v1", img)
    store.approve("prop-cookie-jar-v1")
    cand = _png(tmp_project / "cand.png", (180, 110, 60))
    report = compare_to_canon(
        series_id="likkle-jay",
        candidate_file=cand,
        parent_asset_id="prop-cookie-jar-v1",
        root=tmp_project,
    )
    assert report["review_required"] is True
    assert report["identity_claim"] is False
    assert report["image_similarity"] is not None


def test_readiness_still_fails(tmp_project):
    report = evaluate_season_production_ready("likkle-jay", root=tmp_project)
    assert report.engineering_ready is True
    assert report.season_production_ready is False
