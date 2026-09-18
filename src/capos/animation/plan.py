"""Simple animation planning — camera, character, prop motion."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MotionType(StrEnum):
    CAMERA_PAN = "CAMERA_PAN"
    SLOW_ZOOM = "SLOW_ZOOM"
    PARALLAX = "PARALLAX"
    CHARACTER_TRANSLATION = "CHARACTER_TRANSLATION"
    BLINK = "BLINK"
    MOUTH_MOVEMENT = "MOUTH_MOVEMENT"
    HEAD_MOVEMENT = "HEAD_MOVEMENT"
    ARM_MOVEMENT = "ARM_MOVEMENT"
    PROP_MOVEMENT = "PROP_MOVEMENT"
    REACTION_POSE = "REACTION_POSE"
    TRANSITION_FRAME = "TRANSITION_FRAME"
    HOLD = "HOLD"


class MotionCue(BaseModel):
    cue_id: str
    motion: MotionType
    target: str = ""  # character/prop/camera
    start_frame_id: str
    end_frame_id: str | None = None
    duration_ms: int = 500
    params: dict[str, Any] = Field(default_factory=dict)
    keep: list[str] = Field(
        default_factory=lambda: ["background", "hair", "face_design", "clothes", "props", "camera"]
    )
    change: list[str] = Field(default_factory=list)


class AnimationPlan(BaseModel):
    episode_id: str
    cues: list[MotionCue] = Field(default_factory=list)
    fps: int = 12
    notes: str = "Simple animation first; richer motion later."

    def add_hold(self, frame_id: str, duration_ms: int = 1200) -> None:
        self.cues.append(
            MotionCue(
                cue_id=f"hold_{frame_id}",
                motion=MotionType.HOLD,
                start_frame_id=frame_id,
                duration_ms=duration_ms,
                change=[],
            )
        )
