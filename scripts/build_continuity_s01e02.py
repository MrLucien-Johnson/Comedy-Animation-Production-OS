#!/usr/bin/env python3
"""Build continuity.json for Likkle Jay S01E02 Di Cookie Jar."""

from __future__ import annotations

from capos.core.schemas import FrameManifest
from capos.core.status import ComedyBeat, FrameType
from capos.domain.continuity import (
    build_frame_sequence,
    cookie_jar_episode2_plan,
    initial_kitchen_continuity,
)
from capos.domain.series import load_script, load_storyboard
from capos.pipeline.workflow import write_continuity_file

BEAT_BY_FRAME = {
    "s01e02_f01": ComedyBeat.SETUP,
    "s01e02_f02": ComedyBeat.TEMPTATION,
    "s01e02_f03": ComedyBeat.ESCALATION,
    "s01e02_f04": ComedyBeat.ESCALATION,
    "s01e02_f05": ComedyBeat.DISCOVERY,
    "s01e02_f06": ComedyBeat.REACTION,
    "s01e02_f07": ComedyBeat.PUNCHLINE,
}


def main() -> None:
    storyboard = load_storyboard("likkle-jay", "s01e02")
    script = load_script("likkle-jay", "s01e02")
    lines = {ln.line_id: ln for ln in script.lines}
    frames: list[FrameManifest] = []
    for beat in storyboard:
        dialogue = None
        locked = False
        if beat.dialogue_line_id and beat.dialogue_line_id in lines:
            dialogue = lines[beat.dialogue_line_id].text
            locked = lines[beat.dialogue_line_id].locked
        frames.append(
            FrameManifest(
                frame_id=beat.frame_id or beat.beat_id,
                series_id="likkle-jay",
                season_id="s01",
                episode_id="s01e02",
                scene_id="kitchen-1",
                shot_id=beat.beat_id,
                frame_type=FrameType.DIALOGUE if dialogue else FrameType.KEYFRAME,
                comedy_beat=BEAT_BY_FRAME.get(beat.frame_id or "", beat.comedy_beat),
                action=beat.summary,
                dialogue=dialogue,
                dialogue_locked=locked,
                characters=list(beat.characters),
            )
        )
    # Auntie Bev joins from frame 5 — extend continuity changes
    changes = cookie_jar_episode2_plan()
    changes["s01e02_f05"] = {
        **changes.get("s01e02_f05", {}),
        "character_updates": [],
        "notes": ["Auntie Bev enters — discovery beat"],
    }
    # Add Auntie to initial? Better: inject via character list on frame 5 by extending state
    seq = build_frame_sequence(
        frames,
        initial=initial_kitchen_continuity(),
        changes_by_frame=changes,
    )
    # Manually append Auntie Bev from frame 5 onward for continuity visibility
    from capos.core.schemas import CharacterInstance

    bev = CharacterInstance(
        character_id="auntie-bev",
        canonical_asset_id="character-auntie-bev-v1",
        outfit_asset_id="outfit-auntie-bev-default-v1",
        expression="stern",
        pose="doorway",
        visible=True,
    )
    for fr in seq:
        if fr.frame_id >= "s01e02_f05":
            ids = {c.character_id for c in fr.continuity.characters}
            if "auntie-bev" not in ids:
                fr.continuity.characters.append(bev)
                fr.characters = [c.character_id for c in fr.continuity.characters]
                fr.character_reference_ids = [c.canonical_asset_id for c in fr.continuity.characters]

    path = write_continuity_file("likkle-jay", "s01e02", seq)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
