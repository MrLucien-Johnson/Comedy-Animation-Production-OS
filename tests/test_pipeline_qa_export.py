"""Generation, compositing, QA, export tests."""

from __future__ import annotations

import pytest

from capos.audio.interfaces import cues_from_script, write_srt, write_vtt
from capos.comedy.structure import validate_comedy_arc
from capos.composition.text import apply_speech_bubble, apply_watermark
from capos.core.errors import ExportBlockedError
from capos.core.schemas import WATERMARK_EXACT, FrameManifest
from capos.core.status import ComedyBeat, FrameType, QAResultStatus, StageStatus
from capos.domain.continuity import (
    build_frame_sequence,
    cookie_jar_episode2_plan,
    initial_kitchen_continuity,
)
from capos.domain.series import load_script
from capos.generation.registry import get_backend
from capos.pipeline.workflow import export_episode, new_episode_state, run_episode_frame_qa
from capos.qa.validators import run_frame_qa


def test_mock_generate_creates_file(tmp_project):
    backend = get_backend("mock")
    out = tmp_project / "assets/generations/t.png"
    result = backend.generate_image(prompt="test", width=256, height=256, output_path=out, seed=1)
    assert result.success is True
    assert out.is_file()
    assert result.metadata.get("non_production") is True


def test_watermark_compositor_exact(tmp_project):
    backend = get_backend("mock")
    src = tmp_project / "assets/generations/base.png"
    backend.generate_image(prompt="x", width=256, height=256, output_path=src)
    out = tmp_project / "assets/generations/wm.png"
    text = apply_watermark(src, out)
    assert text == WATERMARK_EXACT
    assert out.is_file()


def test_dialogue_compositor_exact(tmp_project):
    backend = get_backend("mock")
    src = tmp_project / "assets/generations/base2.png"
    backend.generate_image(prompt="x", width=512, height=512, output_path=src)
    locked = "MI NEVA DO NUTTN!"
    out = tmp_project / "assets/generations/dlg.png"
    written = apply_speech_bubble(src, out, dialogue=locked)
    assert written == locked


def test_qa_fail_closed_export(tmp_project):
    state = new_episode_state("s01e02")
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
    state.frames = build_frame_sequence(
        frames,
        initial=initial_kitchen_continuity(),
        changes_by_frame=cookie_jar_episode2_plan(),
    )
    # No images / watermarks → QA not all PASS
    state = run_episode_frame_qa(state)
    assert state.export_blocked is True
    with pytest.raises(ExportBlockedError):
        export_episode(
            state,
            frame_paths=[],
            output_path=str(tmp_project / "assets/exports/ep.mp4"),
        )


def test_qa_watermark_fail():
    frame = build_frame_sequence(
        [
            FrameManifest(
                frame_id="s01e02_f01",
                series_id="likkle-jay",
                season_id="s01",
                episode_id="s01e02",
                frame_type=FrameType.KEYFRAME,
                width=256,
                height=256,
            )
        ],
        initial=initial_kitchen_continuity(),
    )[0]
    report = run_frame_qa(frame, watermark_text="MRLUCIENJONSSON")
    wm = next(c for c in report.checks if c.check_id == "WATERMARK_CHECK")
    assert wm.status == QAResultStatus.FAIL


def test_subtitles_from_script(tmp_project):
    script = load_script("likkle-jay", "s01e02", root=tmp_project)
    cues = cues_from_script(script)
    assert cues[0].text == "JUST ONE COOKIE..."
    srt = write_srt(cues, tmp_project / "assets/exports/ep.srt")
    vtt = write_vtt(cues, tmp_project / "assets/exports/ep.vtt")
    assert "JUST ONE COOKIE..." in srt.read_text()
    assert "WEBVTT" in vtt.read_text()
    assert "MI NEVA DO NUTTN!" in srt.read_text()


def test_comedy_arc_warnings():
    warnings = validate_comedy_arc([ComedyBeat.SETUP])
    assert any("PUNCHLINE" in w for w in warnings)


def test_episode_state_transitions():
    state = new_episode_state("s01e02")
    from capos.core.status import ProductionStage
    from capos.pipeline.workflow import advance_stage

    advance_stage(state, ProductionStage.SCRIPT, StageStatus.READY)
    assert state.stage_map()[ProductionStage.SCRIPT].status == StageStatus.READY
