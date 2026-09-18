"""Canonical reference versioning."""

from __future__ import annotations

import pytest

from capos.core.errors import ValidationError
from capos.core.schemas import CanonicalAssetRef
from capos.core.status import StageStatus
from capos.references.versioning import ReferenceStore, asset_id_for


def test_asset_id_format():
    assert asset_id_for("character", "likkle-jay", 1) == "character-likkle-jay-v1"


def test_cannot_overwrite_approved(tmp_project):
    store = ReferenceStore("likkle-jay", root=tmp_project)
    ref = store.get("prop-cookie-jar-v1")
    assert ref is not None
    store.approve("prop-cookie-jar-v1")
    with pytest.raises(ValidationError):
        store.register(
            CanonicalAssetRef(
                asset_id="prop-cookie-jar-v1",
                kind="prop",
                slug="cookie-jar",
                version=1,
                status=StageStatus.DRAFT,
                metadata={"label": "COOKIE"},
            )
        )


def test_create_new_version(tmp_project):
    store = ReferenceStore("likkle-jay", root=tmp_project)
    store.approve("prop-cookie-jar-v1")
    store.lock_as_canon("prop-cookie-jar-v1")
    new = store.create_new_version("prop-cookie-jar-v1")
    assert new.asset_id == "prop-cookie-jar-v2"
    assert new.version == 2
    old = store.get("prop-cookie-jar-v1")
    assert old is not None
    assert old.status == StageStatus.SUPERSEDED
    assert old.superseded_by == "prop-cookie-jar-v2"
    # label exactness still enforced at prop json level
    import json

    from capos.qa.validators import assert_cookie_label_exact

    prop = json.loads((tmp_project / "series/likkle-jay/props/cookie-jar/prop.json").read_text())
    assert_cookie_label_exact(prop["label"])
