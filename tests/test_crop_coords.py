"""Tests for display ↔ original crop coordinate mapping and visual-crop provenance."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from capos.core.errors import ValidationError
from capos.core.status import CanonStatus, VisualReferenceType
from capos.references.crop_coords import (
    COORDINATE_MISMATCH_CAUSE,
    compute_display_scale,
    map_display_box_to_original,
    open_rgb_corrected,
)
from capos.references.derived_crop import (
    CropBox,
    character_isolation_gate,
    create_derived_character_crop,
    delete_candidate_derived,
)
from capos.references.ingestion import VisualReferenceStore


def _sheet(path: Path, size=(1254, 1254)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Distinct regions: logo top-left, character-ish mid-top
    img = Image.new("RGB", size, (240, 220, 190))
    for x in range(0, 200):
        for y in range(0, 120):
            img.putpixel((x, y), (20, 20, 20))  # logo block
    for x in range(220, 420):
        for y in range(140, 620):
            img.putpixel((x, y), (200, 140, 60))  # fake Jay region
    img.save(path)
    return path


def test_coordinate_mismatch_cause_documents_display_vs_original():
    assert "display" in COORDINATE_MISMATCH_CAUSE.lower() or "Display" in COORDINATE_MISMATCH_CAUSE
    assert "1254" in COORDINATE_MISMATCH_CAUSE or "original" in COORDINATE_MISMATCH_CAUSE.lower()


def test_compute_display_scale_1254_matches_cropper_algorithm():
    scale = compute_display_scale(1254, 1254, max_width=700, max_height=700)
    assert scale.original_width == 1254
    assert scale.original_height == 1254
    assert scale.display_width == 700
    assert scale.display_height == 700
    assert abs(scale.scale_x - (1254 / 700)) < 1e-9
    assert abs(scale.scale_y - (1254 / 700)) < 1e-9


def test_map_display_box_to_original_roundtrip():
    scale = compute_display_scale(1254, 1254)
    # Operator selects ~Jay region on the 700×700 display canvas
    mapped = map_display_box_to_original(
        left=120,
        top=80,
        width=110,
        height=260,
        scale=scale,
    )
    assert mapped["left"] == round(120 * scale.scale_x)
    assert mapped["top"] == round(80 * scale.scale_y)
    assert mapped["right"] <= 1254
    assert mapped["bottom"] <= 1254
    assert mapped["width"] == mapped["right"] - mapped["left"]
    assert mapped["height"] == mapped["bottom"] - mapped["top"]
    # Must NOT land in logo-only tiny corner when mapped from mid display
    assert mapped["left"] > 100
    assert mapped["bottom"] - mapped["top"] > 200


def test_map_display_box_clamps_and_rejects_invalid():
    scale = compute_display_scale(1254, 1254)
    mapped = map_display_box_to_original(
        left=680,
        top=680,
        width=50,
        height=50,
        scale=scale,
    )
    assert mapped["right"] <= 1254
    assert mapped["bottom"] <= 1254
    with pytest.raises(ValidationError):
        map_display_box_to_original(left=0, top=0, width=0, height=10, scale=scale)


def test_logo_guess_vs_mapped_jay_region(tmp_project):
    """Reproduce the failure mode: raw 115,55,215,270 hits logo; mapped display mid does not."""
    path = _sheet(tmp_project / "sheet.png")
    img = open_rgb_corrected(path)
    logo_guess = CropBox(115, 55, 215, 270)
    # Synthetic sheet paints logo (20,20,20) in 0..200×0..120 — this guess overlaps that block
    logo_top = img.crop((logo_guess.left, logo_guess.top, logo_guess.right, 120))
    top_pixels = list(logo_top.getdata())
    dark = sum(1 for p in top_pixels if p == (20, 20, 20))
    assert dark / len(top_pixels) > 0.8
    # Same box must NOT include the painted Jay region (200,140,60) at x≥220
    logo_crop = img.crop((logo_guess.left, logo_guess.top, logo_guess.right, logo_guess.bottom))
    jay_color = sum(1 for p in logo_crop.getdata() if p == (200, 140, 60))
    assert jay_color == 0

    scale = compute_display_scale(1254, 1254)
    mapped = map_display_box_to_original(left=123, top=78, width=112, height=268, scale=scale)
    jay = img.crop((mapped["left"], mapped["top"], mapped["right"], mapped["bottom"]))
    jay_pixels = list(jay.getdata())
    jay_hits = sum(1 for p in jay_pixels if p == (200, 140, 60))
    assert jay_hits / len(jay_pixels) > 0.3
    assert mapped["width"] > logo_guess.as_dict()["width"]
    assert mapped["left"] != logo_guess.left or mapped["top"] != logo_guess.top


def test_aspect_ratio_preserved_in_mapping():
    scale = compute_display_scale(1254, 1254)
    mapped = map_display_box_to_original(left=100, top=50, width=80, height=240, scale=scale)
    display_ar = 80 / 240
    original_ar = mapped["width"] / mapped["height"]
    assert abs(display_ar - original_ar) < 0.02


def test_derived_crop_provenance_and_untouched_original(tmp_project):
    store = VisualReferenceStore("likkle-jay", root=tmp_project)
    src = _sheet(tmp_project / "character-likkle-jay-v1.png")
    original = src.read_bytes()
    ref = store.import_reference(
        src,
        reference_type=VisualReferenceType.STYLE_REFERENCE,
        reference_id="character-likkle-jay-v1",
    )
    store.approve_reference(ref.reference_id)
    scale = compute_display_scale(1254, 1254)
    mapped = map_display_box_to_original(left=123, top=78, width=112, height=268, scale=scale)
    derived = create_derived_character_crop(
        store,
        source_reference_id="character-likkle-jay-v1",
        crop=CropBox(mapped["left"], mapped["top"], mapped["right"], mapped["bottom"]),
        display_mapping={"mapped_audit": mapped},
    )
    assert Path(ref.file).read_bytes() == original
    assert derived.provenance["original_source_dimensions"] == {"width": 1254, "height": 1254}
    assert derived.provenance["coordinate_space"] == "ORIGINAL_IMAGE_PIXELS"
    assert derived.provenance["source_sha256"] == ref.checksum
    assert derived.provenance["crop_coordinates_original_pixels"]["left"] == mapped["left"]
    assert derived.status == CanonStatus.CANDIDATE
    # aspect ratio of crop is positive
    c = derived.provenance["crop_coordinates_original_pixels"]
    assert c["width"] / c["height"] > 0.2


def test_redo_crop_replaces_candidate_not_approved(tmp_project):
    store = VisualReferenceStore("likkle-jay", root=tmp_project)
    src = _sheet(tmp_project / "character-likkle-jay-v1.png")
    ref = store.import_reference(
        src,
        reference_type=VisualReferenceType.CHARACTER_REFERENCE,
        reference_id="character-likkle-jay-v1",
    )
    store.approve_reference(ref.reference_id)
    d1 = create_derived_character_crop(
        store,
        source_reference_id="character-likkle-jay-v1",
        crop=CropBox(220, 140, 420, 620),
    )
    first_checksum = d1.checksum
    d2 = create_derived_character_crop(
        store,
        source_reference_id="character-likkle-jay-v1",
        crop=CropBox(230, 150, 410, 600),
        allow_replace_candidate=True,
    )
    assert d2.checksum != first_checksum
    assert d2.provenance.get("redo_crop") is True
    store.approve_reference(d2.reference_id)
    with pytest.raises(ValidationError, match="APPROVED"):
        create_derived_character_crop(
            store,
            source_reference_id="character-likkle-jay-v1",
            crop=CropBox(200, 100, 400, 500),
            allow_replace_candidate=True,
        )


def test_delete_candidate_derived_and_gate(tmp_project):
    store = VisualReferenceStore("likkle-jay", root=tmp_project)
    src = _sheet(tmp_project / "character-likkle-jay-v1.png")
    ref = store.import_reference(
        src,
        reference_type=VisualReferenceType.CHARACTER_REFERENCE,
        reference_id="character-likkle-jay-v1",
    )
    store.approve_reference(ref.reference_id)
    create_derived_character_crop(
        store,
        source_reference_id="character-likkle-jay-v1",
        crop=CropBox(220, 140, 420, 620),
    )
    gate = character_isolation_gate(store)
    assert gate["ready"] is False
    assert gate["stop"] == "AWAITING_DERIVED_REFERENCE_APPROVAL"
    delete_candidate_derived(store)
    assert store.get("character-likkle-jay-front-derived-v1") is None


def test_open_rgb_corrected_dimensions(tmp_project):
    path = _sheet(tmp_project / "sheet.png")
    img = open_rgb_corrected(path)
    assert img.size == (1254, 1254)
    assert img.mode == "RGB"


def test_invalid_crop_boundaries(tmp_project):
    store = VisualReferenceStore("likkle-jay", root=tmp_project)
    src = _sheet(tmp_project / "character-likkle-jay-v1.png")
    ref = store.import_reference(
        src,
        reference_type=VisualReferenceType.STYLE_REFERENCE,
        reference_id="character-likkle-jay-v1",
    )
    store.approve_reference(ref.reference_id)
    with pytest.raises(ValidationError):
        create_derived_character_crop(
            store,
            source_reference_id="character-likkle-jay-v1",
            crop=CropBox(0, 0, 10, 10),  # too small
        )
    with pytest.raises(ValidationError):
        create_derived_character_crop(
            store,
            source_reference_id="character-likkle-jay-v1",
            crop=CropBox(-1, 0, 100, 100),
        )
