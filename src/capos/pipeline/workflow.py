"""Season / episode production workflow with explicit stage statuses."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from capos.core.errors import ExportBlockedError
from capos.core.schemas import EpisodeState, FrameManifest, QAReport
from capos.core.status import PIPELINE_ORDER, ProductionStage, QAResultStatus, StageStatus
from capos.domain.continuity import continuity_manifest
from capos.domain.series import save_json
from capos.export.ffmpeg_export import ExportRequest, assemble_slideshow
from capos.qa.validators import apply_qa_to_frame, run_frame_qa


def new_episode_state(episode_id: str) -> EpisodeState:
    stages = [{"stage": s, "status": StageStatus.PENDING} for s in PIPELINE_ORDER]
    return EpisodeState(episode_id=episode_id, stages=stages)  # type: ignore[arg-type]


def advance_stage(
    state: EpisodeState, stage: ProductionStage, status: StageStatus, notes: str = ""
) -> EpisodeState:
    state.set_stage(stage, status, notes)
    return state


def run_episode_frame_qa(
    state: EpisodeState,
    *,
    image_paths: dict[str, Path] | None = None,
    watermark_by_frame: dict[str, str] | None = None,
    dialogue_by_frame: dict[str, str] | None = None,
    required_props: list[str] | None = None,
    expected_prop_states: dict[str, dict[str, str]] | None = None,
) -> EpisodeState:
    image_paths = image_paths or {}
    watermark_by_frame = watermark_by_frame or {}
    dialogue_by_frame = dialogue_by_frame or {}
    expected_prop_states = expected_prop_states or {}
    reports: list[QAReport] = []
    updated_frames: list[FrameManifest] = []
    for frame in state.frames:
        report = run_frame_qa(
            frame,
            image_path=image_paths.get(frame.frame_id),
            watermark_text=watermark_by_frame.get(frame.frame_id),
            rendered_dialogue=dialogue_by_frame.get(frame.frame_id),
            required_props=required_props,
            expected_prop_states=expected_prop_states.get(frame.frame_id),
        )
        frame = apply_qa_to_frame(frame, report)
        updated_frames.append(frame)
        reports.append(report)
    state.frames = updated_frames
    state.qa_reports = reports
    all_pass = bool(reports) and all(
        r.overall == QAResultStatus.PASS or r.human_override for r in reports
    )
    # Visual NOT_CHECKED must not count as PASS for export
    state.export_blocked = not all_pass
    state.set_stage(
        ProductionStage.FRAME_QA,
        StageStatus.QA_PASSED if all_pass else StageStatus.QA_FAILED,
    )
    return state


def export_episode(
    state: EpisodeState,
    *,
    frame_paths: list[str],
    output_path: str,
    human_override: bool = False,
    override_reason: str | None = None,
) -> dict[str, Any]:
    if state.export_blocked and not human_override:
        raise ExportBlockedError(
            f"Episode {state.episode_id} export blocked — unresolved QA",
            hint="Fix QA_FAILED frames or pass explicit human_override with reason.",
        )
    if human_override:
        state.human_override = True
        for r in state.qa_reports:
            r.human_override = True
            r.override_reason = override_reason
    req = ExportRequest(
        episode_id=state.episode_id,
        frame_paths=frame_paths,
        output_path=output_path,
        qa_all_passed=not state.export_blocked,
        human_override=human_override,
    )
    result = assemble_slideshow(req)
    if result.get("success"):
        state.set_stage(ProductionStage.FINAL_MP4, StageStatus.EXPORTED)
        state.set_stage(ProductionStage.PUBLISHABLE_EXPORT, StageStatus.REQUIRES_REVIEW)
    return result


def write_continuity_file(
    series_id: str, episode_id: str, frames: list[FrameManifest], *, root: Path | None = None
) -> Path:
    from capos.core.paths import series_dir

    path = series_dir(series_id, root=root) / "episodes" / episode_id / "continuity.json"
    save_json(path, continuity_manifest(frames))
    return path
