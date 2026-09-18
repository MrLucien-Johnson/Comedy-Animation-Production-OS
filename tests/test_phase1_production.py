"""Phase 1 production activation tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from capos.canon.bootstrap import bootstrap_likkle_jay_canon
from capos.composition.masters import PROP_LABEL_COOKIES, SPEECH_BUBBLE, WATERMARK
from capos.core.errors import ValidationError
from capos.core.schemas import COOKIE_LABEL_EXACT, WATERMARK_EXACT, FrameManifest
from capos.core.status import (
    CanonStatus,
    FrameType,
    PropState,
    ProviderAvailability,
    QAResultStatus,
)
from capos.domain.continuity import (
    build_frame_sequence,
    cookie_jar_episode2_plan,
    initial_kitchen_continuity,
)
from capos.generation.null_backend import NullBackend
from capos.generation.provider_status import classify_backend, provider_dashboard_status
from capos.generation.registry import get_backend, record_provider_refusal
from capos.pipeline.readiness import evaluate_season_production_ready
from capos.qa.visual import average_hash, perceptual_similarity_check
from capos.references.golden import GoldenFrameStore
from capos.scale.system import (
    absolute_vs_baseline,
    compile_scale_prompt_block,
    load_scale,
    save_scale,
)
from capos.spatial.layout import (
    compile_spatial_prompt_block,
    load_location_space,
    write_default_spaces,
)


def _png(path: Path, color=(180, 120, 60)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (128, 128), color).save(path)
    return path


def test_bootstrap_does_not_claim_images(tmp_project):
    result = bootstrap_likkle_jay_canon(root=tmp_project)
    assert result["images_created"] == 0
    assert result["images_claimed"] is False
    assert "character-likkle-jay-v1" in result["registry_entries"]
    assert "turnaround-likkle-jay-front-v1" in result["registry_entries"]
    assert "style-likkle-jay-v1" in result["registry_entries"]


def test_golden_reference_required(tmp_project):
    store = GoldenFrameStore("likkle-jay", root=tmp_project)
    g = store.ensure_s01e02_open_jar_placeholder()
    assert g.status == CanonStatus.REFERENCE_REQUIRED
    assert g.file is None
    with pytest.raises(ValidationError):
        store.lock_as_golden(g.golden_id)


def test_golden_lock_after_upload(tmp_project):
    store = GoldenFrameStore("likkle-jay", root=tmp_project)
    g = store.ensure_s01e02_open_jar_placeholder()
    img = _png(tmp_project / "golden_open.png")
    store.attach_and_candidate(g.golden_id, img)
    locked = store.lock_as_golden(g.golden_id)
    assert locked.status == CanonStatus.APPROVED
    assert locked.file


def test_scale_inheritance(tmp_project):
    save_scale(load_scale("likkle-jay"), root=tmp_project)
    manifest = load_scale("likkle-jay", root=tmp_project)
    jar = absolute_vs_baseline(manifest, "cookie-jar-height")
    cookie = absolute_vs_baseline(manifest, "cookie-diameter")
    assert jar < 1.0
    assert cookie < jar
    block = compile_scale_prompt_block(manifest)
    assert "cookie-jar-height" in block
    assert "Baseline unit" in block


def test_spatial_inheritance(tmp_project):
    write_default_spaces("likkle-jay", root=tmp_project)
    space = load_location_space("likkle-jay", "kitchen", root=tmp_project)
    block = compile_spatial_prompt_block(space, prop_regions={"cookie-jar": "LEFT_COUNTER"})
    assert "LEFT_COUNTER" in block
    assert "occupying locked region" in block
    assert "somewhere on counter" in block  # in the prohibition sentence


def test_episode2_open_lid_right():
    frames = [
        FrameManifest(
            frame_id=f"s01e02_f{i:02d}",
            series_id="likkle-jay",
            season_id="s01",
            episode_id="s01e02",
            frame_type=FrameType.KEYFRAME,
        )
        for i in range(1, 4)
    ]
    seq = build_frame_sequence(
        frames,
        initial=initial_kitchen_continuity(),
        changes_by_frame=cookie_jar_episode2_plan(),
    )
    assert seq[0].continuity.props[0].state == PropState.CLOSED
    assert seq[2].continuity.props[0].state == PropState.OPEN_LID_RIGHT
    assert "LEFT_COUNTER" in seq[2].continuity.props[0].position


def test_provider_failure_null():
    backend = NullBackend()
    ok, reason = backend.available()
    assert ok is False
    result = backend.generate_image(prompt="x")
    assert result.success is False


def test_provider_refusal_logged(tmp_project):
    path = record_provider_refusal(
        backend="huggingface",
        prompt="test prompt",
        refusal="content policy",
        log_dir=tmp_project / "logs" / "refusals",
    )
    assert path.is_file()
    text = path.read_text()
    assert "PROVIDER_REFUSED" in text


def test_provider_status_classification():
    assert (
        classify_backend("huggingface", {"available": False, "reason": "HF_TOKEN not set"})
        == ProviderAvailability.NOT_CONFIGURED
    )
    assert (
        classify_backend("mock", {"available": True, "reason": "ok"})
        == ProviderAvailability.AVAILABLE
    )
    rows = provider_dashboard_status()
    names = {r["name"] for r in rows}
    assert "mock" in names


def test_text_masters_exact(tmp_project):
    assert PROP_LABEL_COOKIES.exact() == COOKIE_LABEL_EXACT
    get_backend("mock")
    src = _png(tmp_project / "t.png")
    out = tmp_project / "wm.png"
    assert WATERMARK.apply(src, out) == WATERMARK_EXACT
    dlg = SPEECH_BUBBLE.render(src, tmp_project / "d.png", dialogue="MI NEVA DO NUTTN!")
    assert dlg == "MI NEVA DO NUTTN!"


def test_visual_qa_review_required(tmp_project):
    a = _png(tmp_project / "a.png", (200, 100, 50))
    b = _png(tmp_project / "b.png", (200, 100, 50))
    ha = average_hash(a)
    assert isinstance(ha, str) and len(ha) > 0
    result = perceptual_similarity_check(a, b)
    assert result.status == QAResultStatus.REQUIRES_HUMAN_REVIEW
    assert result.details.get("identity_claimed") is False


def test_season_production_ready_fails_without_canon(tmp_project):
    bootstrap_likkle_jay_canon(root=tmp_project)
    report = evaluate_season_production_ready("likkle-jay", root=tmp_project)
    assert report.season_production_ready is False
    assert report.engineering_ready is True
    assert report.content_ready is False
    assert any(
        c.check_id.startswith("ASSET:") and c.status == QAResultStatus.FAIL for c in report.checks
    )
