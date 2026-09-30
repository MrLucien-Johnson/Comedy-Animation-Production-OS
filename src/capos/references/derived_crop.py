"""Derived character reference crops — original sheet untouched."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from capos.core.errors import ValidationError
from capos.core.schemas import utcnow
from capos.core.status import CanonStatus, VisualReferenceType
from capos.generation.image_validate import validate_candidate_image
from capos.production.storage import sha256_file
from capos.references.crop_coords import open_rgb_corrected
from capos.references.ingestion import VisualReference, VisualReferenceStore


class CropBox:
    """Pixel crop box: left, top, right, bottom (exclusive right/bottom like PIL)."""

    def __init__(self, left: int, top: int, right: int, bottom: int) -> None:
        self.left = int(left)
        self.top = int(top)
        self.right = int(right)
        self.bottom = int(bottom)

    def as_dict(self) -> dict[str, int]:
        return {
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
            "width": self.right - self.left,
            "height": self.bottom - self.top,
        }

    def validate_against(self, width: int, height: int) -> None:
        if self.left < 0 or self.top < 0 or self.right > width or self.bottom > height:
            raise ValidationError(
                f"Crop box {self.as_dict()} exceeds image bounds {width}x{height}"
            )
        if self.right <= self.left or self.bottom <= self.top:
            raise ValidationError("Crop box must have positive width and height")
        if (self.right - self.left) < 32 or (self.bottom - self.top) < 32:
            raise ValidationError("Crop too small — need a readable full-body figure")


def create_derived_character_crop(
    store: VisualReferenceStore,
    *,
    source_reference_id: str,
    crop: CropBox,
    derived_id: str = "character-likkle-jay-front-derived-v1",
    notes: str = "Front-facing full-body Likkle Jay isolated from character sheet",
    allow_replace_candidate: bool = False,
    display_mapping: dict[str, Any] | None = None,
) -> VisualReference:
    """Crop a clean character figure from an approved sheet. Never modifies the source file.

    If ``allow_replace_candidate`` and an existing derived ref is still CANDIDATE (not
    APPROVED), replace its file/metadata for REDO CROP. APPROVED derived refs are never
    overwritten.
    """
    source = store.get(source_reference_id)
    if not source:
        for ref in store.list_references():
            if (
                source_reference_id in ref.reference_id
                or source_reference_id in Path(ref.file).name
                or source_reference_id.replace(".png", "") in Path(ref.file).stem
            ):
                source = ref
                break
    if not source:
        raise ValidationError(
            f"Source reference not found: {source_reference_id}",
            hint="Import/approve character-likkle-jay-v1 first",
        )
    src_path = Path(source.file)
    if not src_path.is_file():
        raise ValidationError(f"Source file missing: {src_path}")

    existing = store.get(derived_id)
    if existing:
        if existing.status == CanonStatus.APPROVED:
            raise ValidationError(
                f"Derived reference {derived_id} is APPROVED — create a new version id instead of overwrite",
            )
        if not allow_replace_candidate:
            raise ValidationError(
                f"Derived reference {derived_id} already exists — never overwrite",
                hint="Use allow_replace_candidate=True for REDO CROP while status is CANDIDATE",
            )

    source_checksum = source.checksum or sha256_file(src_path)
    img = open_rgb_corrected(src_path)
    w, h = img.size
    crop.validate_against(w, h)
    cropped = img.crop((crop.left, crop.top, crop.right, crop.bottom))

    dest_dir = (
        store.imports_dir
        / VisualReferenceType.DERIVED_CHARACTER_REFERENCE.value.lower()
        / derived_id
    )
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{derived_id}.png"
    if dest.exists() and not (existing and allow_replace_candidate):
        raise ValidationError(f"Destination already exists: {dest}")
    cropped.save(dest, format="PNG")

    validation = validate_candidate_image(dest, require_square=False)
    if not validation["ok"]:
        if not existing:
            dest.unlink(missing_ok=True)
        raise ValidationError(f"Invalid derived image: {validation.get('error')}")

    checksum = sha256_file(dest)
    provenance: dict[str, Any] = {
        "derived": True,
        "source_reference_id": source.reference_id,
        "source_file": str(src_path),
        "source_path": str(src_path),
        "source_sha256": source_checksum,
        "original_source_dimensions": {"width": w, "height": h},
        "crop_coordinates_original_pixels": crop.as_dict(),
        "crop": crop.as_dict(),
        "derived_sha256": checksum,
        "created_at": utcnow().isoformat(),
        "original_untouched": True,
        "auto_canonical": False,
        "coordinate_space": "ORIGINAL_IMAGE_PIXELS",
    }
    if display_mapping:
        provenance["display_mapping"] = display_mapping
    if existing and allow_replace_candidate:
        provenance["replaced_previous_checksum"] = existing.checksum
        provenance["redo_crop"] = True

    ref = VisualReference(
        reference_id=derived_id,
        series_id=store.series_id,
        reference_type=VisualReferenceType.DERIVED_CHARACTER_REFERENCE,
        file=str(dest),
        width=validation.get("width"),
        height=validation.get("height"),
        checksum=checksum,
        notes=notes,
        source="derived_crop",
        provenance=provenance,
        status=CanonStatus.CANDIDATE,
    )
    data = store._load_index()
    data.setdefault("references", {})[derived_id] = ref.model_dump(mode="json")
    store._save_index(data)
    return ref


def delete_candidate_derived(
    store: VisualReferenceStore,
    derived_id: str = "character-likkle-jay-front-derived-v1",
) -> None:
    """Remove a CANDIDATE derived ref so REDO CROP can start clean. Never deletes APPROVED."""
    existing = store.get(derived_id)
    if not existing:
        return
    if existing.status == CanonStatus.APPROVED:
        raise ValidationError("Cannot redo/delete an APPROVED derived reference")
    data = store._load_index()
    data.get("references", {}).pop(derived_id, None)
    store._save_index(data)
    path = Path(existing.file)
    if path.is_file():
        path.unlink()


def find_likkle_jay_sheet_reference(store: VisualReferenceStore) -> VisualReference | None:
    """Locate character-likkle-jay-v1 (or closest) among imported references."""
    preferred_keys = (
        "character-likkle-jay-v1",
        "likkle-jay-v1",
        "character-likkle-jay",
    )
    refs = store.list_references()
    for key in preferred_keys:
        for ref in refs:
            blob = f"{ref.reference_id} {Path(ref.file).name}".lower()
            if key.lower() in blob:
                return ref
    return None


def character_isolation_gate(store: VisualReferenceStore) -> dict[str, Any]:
    """Report whether 2B.1 isolation generation can run."""
    derived = store.get("character-likkle-jay-front-derived-v1")
    sheet = find_likkle_jay_sheet_reference(store)
    ready = bool(
        derived
        and derived.status == CanonStatus.APPROVED
        and Path(derived.file).is_file()
    )
    return {
        "ready": ready,
        "stop": None if ready else "AWAITING_DERIVED_REFERENCE_APPROVAL",
        "original_reference": (
            {
                "reference_id": sheet.reference_id,
                "file": sheet.file,
                "checksum": sheet.checksum,
                "status": sheet.status.value,
                "dimensions": (
                    {"width": sheet.width, "height": sheet.height}
                    if sheet.width and sheet.height
                    else None
                ),
            }
            if sheet
            else None
        ),
        "derived_reference": (
            {
                "reference_id": derived.reference_id,
                "file": derived.file,
                "checksum": derived.checksum,
                "status": derived.status.value,
                "crop": (derived.provenance or {}).get("crop_coordinates_original_pixels")
                or (derived.provenance or {}).get("crop"),
                "original_source_dimensions": (derived.provenance or {}).get(
                    "original_source_dimensions"
                ),
                "source_reference_id": (derived.provenance or {}).get("source_reference_id"),
                "source_sha256": (derived.provenance or {}).get("source_sha256"),
            }
            if derived
            else None
        ),
        "derived_reference_approved": bool(
            derived and derived.status == CanonStatus.APPROVED
        ),
        "preferred_derived_id": "character-likkle-jay-front-derived-v1",
        "ui_action": (
            "Streamlit → References → CREATE DERIVED CHARACTER REFERENCE "
            "(visual crop front-facing full-body Jay) → side-by-side review → "
            "APPROVE DERIVED REFERENCE → then run isolation generation"
        ),
    }
