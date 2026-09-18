"""Continuity engine — reference-locked state inheritance."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from capos.core.errors import ContinuityError, ValidationError
from capos.core.schemas import (
    ContinuityState,
    FrameManifest,
    PropInstance,
    PropState,
)
from capos.core.status import FrameType, StageStatus


def apply_explicit_changes(
    base: ContinuityState,
    changes: dict[str, Any],
) -> ContinuityState:
    """Apply script-declared continuity changes onto an inherited state."""
    state = ContinuityState.model_validate(base.model_dump())

    if "location_id" in changes:
        state.location_id = changes["location_id"]
    if "location_asset_id" in changes:
        state.location_asset_id = changes["location_asset_id"]
    if "time_of_day" in changes:
        state.time_of_day = changes["time_of_day"]
    if "lighting" in changes:
        state.lighting = changes["lighting"]
    if "camera" in changes and isinstance(changes["camera"], dict):
        state.camera = state.camera.model_copy(update=changes["camera"])
    if "dialogue" in changes:
        state.dialogue = changes["dialogue"]
        state.dialogue_locked = bool(changes.get("dialogue_locked", state.dialogue is not None))
    if "notes" in changes:
        state.notes = list(changes["notes"])

    if "prop_updates" in changes:
        by_id = {p.prop_id: p for p in state.props}
        for update in changes["prop_updates"]:
            pid = update["prop_id"]
            if pid not in by_id:
                raise ContinuityError(
                    f"Prop '{pid}' not in inherited continuity",
                    hint="Add the prop in an earlier frame or include it in the initial state.",
                )
            prop = by_id[pid]
            if "state" in update:
                prop.state = PropState(update["state"])
            if "position" in update:
                prop.position = update["position"]
            if "custom_state" in update:
                prop.custom_state = update["custom_state"]
            # Identity (canonical_asset_id) cannot be changed via state update.
            if (
                "canonical_asset_id" in update
                and update["canonical_asset_id"] != prop.canonical_asset_id
            ):
                raise ContinuityError(
                    f"Cannot change prop identity for '{pid}' via continuity update",
                    hint="Episode state may change; canonical identity requires a new asset version.",
                )
        state.props = list(by_id.values())

    if "character_updates" in changes:
        by_id = {c.character_id: c for c in state.characters}
        for update in changes["character_updates"]:
            cid = update["character_id"]
            if cid not in by_id:
                raise ContinuityError(f"Character '{cid}' not in inherited continuity")
            char = by_id[cid]
            for field in ("expression", "pose", "outfit_asset_id", "visible"):
                if field in update:
                    setattr(char, field, update[field])
            if "hair_lock" in update and update["hair_lock"] != char.hair_lock:
                raise ContinuityError(
                    f"Hair lock for '{cid}' is immutable",
                    hint="Hair is a hard continuity lock; do not alter between frames.",
                )
            if (
                "canonical_asset_id" in update
                and update["canonical_asset_id"] != char.canonical_asset_id
            ):
                raise ContinuityError(f"Cannot change character identity for '{cid}'")
        state.characters = list(by_id.values())

    return state


def build_frame_sequence(
    frames: list[FrameManifest],
    *,
    initial: ContinuityState,
    changes_by_frame: dict[str, dict[str, Any]] | None = None,
) -> list[FrameManifest]:
    """
    Walk frames in order; each frame inherits prior continuity unless explicit changes apply.
    """
    changes_by_frame = changes_by_frame or {}
    if not frames:
        return []

    result: list[FrameManifest] = []
    current = ContinuityState.model_validate(initial.model_dump())
    prev_id: str | None = None

    for frame in frames:
        inherited = current.inherit()
        inherited.previous_frame_id = prev_id
        if frame.frame_id in changes_by_frame:
            inherited = apply_explicit_changes(inherited, changes_by_frame[frame.frame_id])
        # Seed dialogue from frame if set
        if frame.dialogue is not None:
            inherited.dialogue = frame.dialogue
            inherited.dialogue_locked = frame.dialogue_locked
        frame.continuity = inherited
        frame.continuity_from = prev_id
        frame.location_reference_id = inherited.location_asset_id
        frame.character_reference_ids = [c.canonical_asset_id for c in inherited.characters]
        frame.prop_reference_ids = [p.canonical_asset_id for p in inherited.props]
        frame.characters = [c.character_id for c in inherited.characters if c.visible]
        frame.camera = inherited.camera
        if inherited.dialogue is not None:
            frame.dialogue = inherited.dialogue
            frame.dialogue_locked = inherited.dialogue_locked
        frame.touch()
        result.append(frame)
        # Link previous next pointer
        if result and len(result) >= 2:
            result[-2].continuity_to = frame.frame_id
            result[-2].continuity.next_frame_id = frame.frame_id
        current = inherited
        current.previous_frame_id = frame.frame_id
        prev_id = frame.frame_id

    return result


def continuity_manifest(frames: list[FrameManifest]) -> dict[str, Any]:
    """Serialize episode continuity.json payload."""
    return {
        "frames": [
            {
                "frame_id": f.frame_id,
                "frame_type": f.frame_type.value
                if isinstance(f.frame_type, FrameType)
                else f.frame_type,
                "status": f.status.value if isinstance(f.status, StageStatus) else f.status,
                "continuity": f.continuity.model_dump(mode="json"),
                "continuity_from": f.continuity_from,
                "continuity_to": f.continuity_to,
            }
            for f in frames
        ]
    }


def assert_prop_identity_stable(frames: list[FrameManifest], prop_id: str) -> None:
    ids = []
    for f in frames:
        for p in f.continuity.props:
            if p.prop_id == prop_id:
                ids.append(p.canonical_asset_id)
    if len(set(ids)) > 1:
        raise ContinuityError(
            f"Prop '{prop_id}' canonical identity drifted across frames: {sorted(set(ids))}"
        )


def cookie_jar_episode2_plan() -> dict[str, dict[str, Any]]:
    """
    Episode 2 (Di Cookie Jar) special continuity:
    Frames 1–2 CLOSED; frames 3+ OPEN with lid beside jar.
    """
    changes: dict[str, dict[str, Any]] = {}
    # Frame 3 introduces OPEN state — identity unchanged.
    changes["s01e02_f03"] = {
        "prop_updates": [
            {
                "prop_id": "cookie-jar",
                "state": PropState.OPEN_LID_RIGHT.value,
                "position": "LEFT_COUNTER; lid beside jar RIGHT of jar",
                "custom_state": "OPEN_LID_RIGHT — episode visual master pending golden upload",
            }
        ],
        "notes": [
            "Episode 2 Frame 3 OPEN cookie-jar continuity; golden reference REFERENCE_REQUIRED until uploaded."
        ],
    }
    return changes


def initial_kitchen_continuity() -> ContinuityState:
    return ContinuityState(
        location_id="kitchen",
        location_asset_id="location-kitchen-v1",
        time_of_day="day",
        lighting="warm indoor kitchen",
        characters=[
            {
                "character_id": "likkle-jay",
                "canonical_asset_id": "character-likkle-jay-v1",
                "outfit_asset_id": "outfit-likkle-jay-default-v1",
                "expression": "curious",
                "hair_lock": "rounded dome of tight black curls, full and consistent",
                "pose": "standing",
                "visible": True,
            }
        ],
        props=[
            PropInstance(
                prop_id="cookie-jar",
                canonical_asset_id="prop-cookie-jar-v1",
                state=PropState.CLOSED,
                position="LEFT_COUNTER",
                scale_notes="cookie-jar-height and cookie-diameter from relative_scale.json",
            )
        ],
    )


def validate_locked_dialogue(frame: FrameManifest, expected: str) -> None:
    if not frame.dialogue_locked:
        return
    if frame.dialogue != expected:
        raise ValidationError(
            "Locked dialogue mismatch",
            hint=f"Expected exact {expected!r}, got {frame.dialogue!r}",
        )


def deep_copy_state(state: ContinuityState) -> ContinuityState:
    return ContinuityState.model_validate(deepcopy(state.model_dump()))
