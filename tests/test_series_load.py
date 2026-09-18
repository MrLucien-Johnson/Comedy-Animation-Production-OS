"""Series loading smoke tests."""

from __future__ import annotations

from capos.domain.series import list_series, load_episode_brief, load_series
from capos.references.versioning import ReferenceStore


def test_likkle_jay_loads(tmp_project):
    assert "likkle-jay" in list_series(root=tmp_project)
    series = load_series("likkle-jay", root=tmp_project)
    assert series.watermark == "MRLUCIENJOHNSON"
    brief = load_episode_brief("likkle-jay", "s01e02", root=tmp_project)
    assert brief.title == "Di Cookie Jar"
    store = ReferenceStore("likkle-jay", root=tmp_project)
    assert store.get("character-likkle-jay-v1") is not None
    assert store.get("prop-cookie-jar-v1") is not None
