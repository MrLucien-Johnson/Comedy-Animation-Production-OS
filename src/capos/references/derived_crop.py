"""Derived character reference crops — original sheet untouched."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from capos.core.errors import ValidationError
from capos.core.schemas import utcnow
from capos.core.status import CanonStatus, VisualReferenceType
from capos.generation.image_validate import validate_candidate_image
from capos.production.storage import sha256_file
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
) -> VisualReference:
    """Crop a clean character figure from an approved sheet. Never modifies the source file."""
    source = store.get(source_reference_id)
    if not source:
        # Also allow matching by filename stem inside any reference
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
        raise ValidationError(
            f"Derived reference {derived_id} already exists — never overwrite",
            hint="Use a new derived_id / version suffix",
        )

    source_checksum = source.checksum or sha256_file(src_path)
    with Image.open(src_path) as img:
        img = img.convert("RGB")
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
    if dest.exists():
        raise ValidationError(f"Destination already exists: {dest}")
    cropped.save(dest, format="PNG")

    validation = validate_candidate_image(dest, require_square=False)
    if not validation["ok"]:
        dest.unlink(missing_ok=True)
        raise ValidationError(f"Invalid derived image: {validation.get('error')}")

    checksum = sha256_file(dest)
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
        provenance={
            "derived": True,
            "source_reference_id": source.reference_id,
            "source_file": str(src_path),
            "source_sha256": source_checksum,
            "crop": crop.as_dict(),
            "derived_sha256": checksum,
            "created_at": utcnow().isoformat(),
            "original_untouched": True,
            "auto_canonical": False,
        },
        status=CanonStatus.CANDIDATE,
    )
    data = store._load_index()
    data.setdefault("references", {})[derived_id] = ref.model_dump(mode="json")
    store._save_index(data)
    return ref


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
                "crop": (derived.provenance or {}).get("crop"),
                "source_reference_id": (derived.provenance or {}).get("source_reference_id"),
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
            "(crop front-facing full-body Jay) → APPROVE REFERENCE → "
            "run scripts/phase2b1_character_isolation.py"
        ),
    }
