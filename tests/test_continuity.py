"""Continuity inheritance and episode 2 cookie jar plan."""

from __future__ import annotations

import pytest

from capos.core.errors import ContinuityError
from capos.core.schemas import FrameManifest, PropState
from capos.core.status import FrameType
from capos.domain.continuity import (
    assert_prop_identity_stable,
    build_frame_sequence,
    cookie_jar_episode2_plan,
    initial_kitchen_continuity,
)


def _frames(n: int = 7) -> list[FrameManifest]:
    return [
        FrameManifest(
            frame_id=f"s01e02_f{i:02d}",
            series_id="likkle-jay",
            season_id="s01",
            episode_id="s01e02",
            frame_type=FrameType.KEYFRAME,
            action=f"frame {i}",
        )
        for i in range(1, n + 1)
    ]


def test_state_inheritance_keeps_jar_closed_until_frame3():
    seq = build_frame_sequence(
        _frames(),
        initial=initial_kitchen_continuity(),
        changes_by_frame=cookie_jar_episode2_plan(),
    )
    assert seq[0].continuity.props[0].state == PropState.CLOSED
    assert seq[1].continuity.props[0].state == PropState.CLOSED
    assert seq[2].continuity.props[0].state == PropState.OPEN
    assert seq[3].continuity.props[0].state == PropState.OPEN
    # Identity stable
    assert_prop_identity_stable(seq, "cookie-jar")
    assert all(
        p.canonical_asset_id == "prop-cookie-jar-v1"
        for f in seq
        for p in f.continuity.props
        if p.prop_id == "cookie-jar"
    )


def test_hair_lock_rejects_change():
    with pytest.raises(ContinuityError):
        build_frame_sequence(
            _frames(2),
            initial=initial_kitchen_continuity(),
            changes_by_frame={
                "s01e02_f02": {
                    "character_updates": [
                        {"character_id": "likkle-jay", "hair_lock": "fade haircut"}
                    ]
                }
            },
        )


def test_prop_identity_cannot_change():
    with pytest.raises(ContinuityError):
        build_frame_sequence(
            _frames(2),
            initial=initial_kitchen_continuity(),
            changes_by_frame={
                "s01e02_f02": {
                    "prop_updates": [
                        {
                            "prop_id": "cookie-jar",
                            "canonical_asset_id": "prop-cookie-jar-v2",
                            "state": "OPEN",
                        }
                    ]
                }
            },
        )


def test_sequence_links():
    seq = build_frame_sequence(_frames(3), initial=initial_kitchen_continuity())
    assert seq[1].continuity_from == "s01e02_f01"
    assert seq[0].continuity_to == "s01e02_f02"
    assert seq[0].location_reference_id == "location-kitchen-v1"
