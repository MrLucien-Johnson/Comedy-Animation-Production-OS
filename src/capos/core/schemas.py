"""Domain schemas for CAPOS."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from capos.core.status import (
    ComedyBeat,
    FrameType,
    ProductionStage,
    PropState,
    QAResultStatus,
    StageStatus,
)

WATERMARK_EXACT = "MRLUCIENJOHNSON"
COOKIE_LABEL_EXACT = "COOKIES"


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return uuid4().hex


class CanonicalAssetRef(BaseModel):
    """Versioned canonical asset pointer. Never silently overwrite approved assets."""

    asset_id: str  # e.g. character-likkle-jay-v1
    kind: str  # character | location | prop | outfit | expression | turnaround
    slug: str
    version: int = 1
    status: StageStatus = StageStatus.DRAFT
    path: str | None = None
    checksum: str | None = None
    superseded_by: str | None = None
    locked_traits: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    def bump_version_id(self) -> str:
        base = self.asset_id.rsplit("-v", 1)[0]
        return f"{base}-v{self.version + 1}"


class CameraState(BaseModel):
    angle: str = "straight-on"
    framing: str = "medium"
    lens_notes: str = ""
    baseline_locked: bool = True


class PropInstance(BaseModel):
    prop_id: str
    canonical_asset_id: str
    state: PropState = PropState.CLOSED
    position: str = ""
    scale_notes: str = "derive from canonical reference"
    custom_state: str | None = None


class CharacterInstance(BaseModel):
    character_id: str
    canonical_asset_id: str
    outfit_asset_id: str | None = None
    expression: str = "neutral"
    hair_lock: str | None = None
    pose: str = ""
    visible: bool = True


class ContinuityState(BaseModel):
    """Episode continuity snapshot for a frame."""

    location_id: str | None = None
    location_asset_id: str | None = None
    time_of_day: str = "day"
    lighting: str = "warm indoor"
    camera: CameraState = Field(default_factory=CameraState)
    characters: list[CharacterInstance] = Field(default_factory=list)
    props: list[PropInstance] = Field(default_factory=list)
    dialogue: str | None = None
    dialogue_locked: bool = False
    previous_frame_id: str | None = None
    next_frame_id: str | None = None
    notes: list[str] = Field(default_factory=list)

    def inherit(self) -> ContinuityState:
        """Return a copy suitable as the next frame's starting state."""
        data = self.model_dump()
        data["previous_frame_id"] = None
        data["next_frame_id"] = None
        # Dialogue does not auto-carry unless explicitly kept.
        data["dialogue"] = None
        data["dialogue_locked"] = False
        return ContinuityState.model_validate(data)


class FrameManifest(BaseModel):
    frame_id: str
    series_id: str
    season_id: str
    episode_id: str
    scene_id: str | None = None
    shot_id: str | None = None
    frame_type: FrameType = FrameType.KEYFRAME
    aspect_ratio: str = "1:1"
    width: int = 1024
    height: int = 1024
    comedy_beat: ComedyBeat | None = None
    characters: list[str] = Field(default_factory=list)
    character_reference_ids: list[str] = Field(default_factory=list)
    location_reference_id: str | None = None
    prop_reference_ids: list[str] = Field(default_factory=list)
    camera: CameraState = Field(default_factory=CameraState)
    action: str = ""
    expression: str = ""
    dialogue: str | None = None
    dialogue_locked: bool = False
    continuity_from: str | None = None
    continuity_to: str | None = None
    continuity: ContinuityState = Field(default_factory=ContinuityState)
    generation_provider: str | None = None
    generation_prompt_version: str | None = None
    source_asset: str | None = None
    checksum: str | None = None
    qa_status: StageStatus = StageStatus.PENDING
    human_approval: StageStatus = StageStatus.PENDING
    status: StageStatus = StageStatus.DRAFT
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    def touch(self) -> None:
        self.updated_at = utcnow()


class QACheckResult(BaseModel):
    check_id: str
    status: QAResultStatus = QAResultStatus.NOT_CHECKED
    message: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class QAReport(BaseModel):
    target_id: str
    checks: list[QACheckResult] = Field(default_factory=list)
    overall: QAResultStatus = QAResultStatus.NOT_CHECKED
    human_override: bool = False
    override_reason: str | None = None
    created_at: datetime = Field(default_factory=utcnow)

    @property
    def can_export(self) -> bool:
        if self.human_override:
            return True
        if not self.checks:
            return False
        return all(c.status == QAResultStatus.PASS for c in self.checks)

    def summarize(self) -> QAResultStatus:
        if not self.checks:
            self.overall = QAResultStatus.NOT_CHECKED
            return self.overall
        statuses = {c.status for c in self.checks}
        if QAResultStatus.FAIL in statuses:
            self.overall = QAResultStatus.FAIL
        elif QAResultStatus.REQUIRES_HUMAN_REVIEW in statuses:
            self.overall = QAResultStatus.REQUIRES_HUMAN_REVIEW
        elif QAResultStatus.NOT_CHECKED in statuses:
            self.overall = QAResultStatus.NOT_CHECKED
        elif statuses == {QAResultStatus.PASS}:
            self.overall = QAResultStatus.PASS
        else:
            self.overall = QAResultStatus.CHECKED
        return self.overall


class GenerationRecord(BaseModel):
    id: str = Field(default_factory=new_id)
    frame_id: str
    series_id: str
    episode_id: str
    backend: str = "mock"
    model: str | None = None
    seed: int | None = None
    positive_prompt: str = ""
    negative_prompt: str = ""
    prompt_version: str | None = None
    width: int = 1024
    height: int = 1024
    status: StageStatus = StageStatus.GENERATED
    output_path: str | None = None
    approved_path: str | None = None
    reference_assets: list[str] = Field(default_factory=list)
    settings: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    refusal: str | None = None
    parent_id: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    def touch(self) -> None:
        self.updated_at = utcnow()


class DialogueLine(BaseModel):
    line_id: str
    speaker: str
    text: str
    locked: bool = False

    @field_validator("text")
    @classmethod
    def non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("dialogue text must be non-empty")
        return v


class ScriptDocument(BaseModel):
    episode_id: str
    title: str
    logline: str = ""
    comedy_structure: list[ComedyBeat] = Field(default_factory=list)
    lines: list[DialogueLine] = Field(default_factory=list)
    status: StageStatus = StageStatus.DRAFT


class StoryboardBeat(BaseModel):
    beat_id: str
    comedy_beat: ComedyBeat
    frame_id: str | None = None
    summary: str
    location_id: str | None = None
    characters: list[str] = Field(default_factory=list)
    props: list[str] = Field(default_factory=list)
    dialogue_line_id: str | None = None


class EpisodeBrief(BaseModel):
    episode_id: str
    series_id: str
    season_id: str
    number: int
    title: str
    premise: str
    engagement_notes: list[str] = Field(default_factory=list)
    target_primary_frames: int | None = 7
    status: StageStatus = StageStatus.DRAFT


class StageProgress(BaseModel):
    stage: ProductionStage
    status: StageStatus = StageStatus.PENDING
    notes: str = ""
    updated_at: datetime = Field(default_factory=utcnow)


class EpisodeState(BaseModel):
    episode_id: str
    stages: list[StageProgress] = Field(default_factory=list)
    frames: list[FrameManifest] = Field(default_factory=list)
    qa_reports: list[QAReport] = Field(default_factory=list)
    export_blocked: bool = True
    human_override: bool = False
    updated_at: datetime = Field(default_factory=utcnow)

    def stage_map(self) -> dict[ProductionStage, StageProgress]:
        return {s.stage: s for s in self.stages}

    def set_stage(self, stage: ProductionStage, status: StageStatus, notes: str = "") -> None:
        existing = self.stage_map()
        if stage in existing:
            existing[stage].status = status
            existing[stage].notes = notes
            existing[stage].updated_at = utcnow()
        else:
            self.stages.append(StageProgress(stage=stage, status=status, notes=notes))
        self.updated_at = utcnow()
