"""Prompt compiler tests."""

from __future__ import annotations

from capos.core.schemas import FrameManifest
from capos.core.status import FrameType
from capos.domain.continuity import build_frame_sequence, initial_kitchen_continuity
from capos.prompts.compiler import PromptCompiler


def test_prompt_contains_locks_and_versions(tmp_project):
    frame = FrameManifest(
        frame_id="s01e02_f01",
        series_id="likkle-jay",
        season_id="s01",
        episode_id="s01e02",
        frame_type=FrameType.KEYFRAME,
        action="Jay looks at jar",
        characters=["likkle-jay"],
    )
    seq = build_frame_sequence([frame], initial=initial_kitchen_continuity())
    compiler = PromptCompiler("likkle-jay", root=tmp_project)
    payload = compiler.compile_frame(seq[0], persist=True)
    assert "rounded dome of tight black curls" in payload["positive"]
    assert "COOKIES" in payload["positive"]
    assert (
        "Do not render speech-bubble lettering" in payload["positive"]
        or "do NOT render" in payload["positive"]
    )
    assert payload["prompt_version"]
    latest = tmp_project / "prompts" / "s01e02_f01" / "latest.json"
    assert latest.is_file()
