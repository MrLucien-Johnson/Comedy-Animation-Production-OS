"""Visual reference ingestion — import existing approved artwork (never overwrite)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from capos.core.errors import ValidationError
from capos.core.paths import series_dir
from capos.core.schemas import utcnow
from capos.core.status import CanonStatus, VisualReferenceType
from capos.generation.image_validate import validate_candidate_image
from capos.production.storage import sha256_file


ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


class VisualReference(BaseModel):
    reference_id: str
    series_id: str
    reference_type: VisualReferenceType
    file: str
    width: int | None = None
    height: int | None = None
    checksum: str
    imported_at: str = Field(default_factory=lambda: utcnow().isoformat())
    status: CanonStatus = CanonStatus.CANDIDATE
    notes: str = ""
    source: str = "user_import"
    provenance: dict[str, Any] = Field(default_factory=dict)


class StyleReferenceSet(BaseModel):
    set_id: str
    series_id: str
    version: str = "v1"
    reference_ids: list[str] = Field(default_factory=list)
    status: CanonStatus = CanonStatus.DRAFT
    notes: str = ""
    created_at: str = Field(default_factory=lambda: utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: utcnow().isoformat())


class VisualReferenceStore:
    """First-class store for imported visual references + curated sets."""

    def __init__(self, series_id: str = "likkle-jay", *, root: Path | None = None) -> None:
        self.series_id = series_id
        self.root = root
        base = series_dir(series_id, root=root) / "visual_references"
        self.base = base
        self.index_path = base / "index.json"
        self.sets_path = base / "sets.json"
        self.imports_dir = base / "imports"
        self.imports_dir.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> dict[str, Any]:
        if not self.index_path.is_file():
            return {"references": {}}
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def _save_index(self, data: dict[str, Any]) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    def _load_sets(self) -> dict[str, Any]:
        if not self.sets_path.is_file():
            return {"sets": {}}
        return json.loads(self.sets_path.read_text(encoding="utf-8"))

    def _save_sets(self, data: dict[str, Any]) -> None:
        self.sets_path.parent.mkdir(parents=True, exist_ok=True)
        self.sets_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    def import_reference(
        self,
        source_path: str | Path,
        *,
        reference_type: VisualReferenceType,
        reference_id: str | None = None,
        notes: str = "",
        source: str = "user_import",
    ) -> VisualReference:
        src = Path(source_path)
        if not src.is_file():
            raise ValidationError(f"Reference file missing: {src}")
        if src.suffix.lower() not in ALLOWED_EXTENSIONS:
            raise ValidationError(
                f"Unsupported extension {src.suffix}",
                hint=f"Use one of: {sorted(ALLOWED_EXTENSIONS)}",
            )
        validation = validate_candidate_image(src, require_square=False)
        if not validation["ok"]:
            raise ValidationError(f"Invalid image: {validation.get('error')}")

        rid = reference_id or f"{reference_type.value.lower()}-{src.stem}-{validation['checksum'][:8]}"
        existing = self.get(rid)
        if existing:
            raise ValidationError(
                f"Reference {rid} already exists — never overwrite",
                hint="Use a new reference_id or create a new set version.",
            )

        dest_dir = self.imports_dir / reference_type.value.lower() / rid
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        if dest.exists():
            raise ValidationError(f"Destination already exists: {dest}")
        shutil.copy2(src, dest)
        checksum = sha256_file(dest)
        ref = VisualReference(
            reference_id=rid,
            series_id=self.series_id,
            reference_type=reference_type,
            file=str(dest),
            width=validation.get("width"),
            height=validation.get("height"),
            checksum=checksum,
            notes=notes,
            source=source,
            provenance={
                "original_filename": src.name,
                "imported_bytes": dest.stat().st_size,
            },
            status=CanonStatus.CANDIDATE,
        )
        data = self._load_index()
        data.setdefault("references", {})[rid] = ref.model_dump(mode="json")
        self._save_index(data)
        return ref

    def get(self, reference_id: str) -> VisualReference | None:
        raw = self._load_index().get("references", {}).get(reference_id)
        return VisualReference.model_validate(raw) if raw else None

    def list_references(
        self, *, reference_type: VisualReferenceType | None = None
    ) -> list[VisualReference]:
        refs = [
            VisualReference.model_validate(v)
            for v in self._load_index().get("references", {}).values()
        ]
        if reference_type:
            refs = [r for r in refs if r.reference_type == reference_type]
        return sorted(refs, key=lambda r: r.imported_at)

    def approve_reference(self, reference_id: str) -> VisualReference:
        ref = self.get(reference_id)
        if not ref:
            raise ValidationError(f"Unknown reference {reference_id}")
        if not Path(ref.file).is_file():
            raise ValidationError("Cannot approve missing file")
        ref.status = CanonStatus.APPROVED
        data = self._load_index()
        data["references"][reference_id] = ref.model_dump(mode="json")
        self._save_index(data)
        return ref

    def create_or_update_set(
        self,
        set_id: str,
        reference_ids: list[str],
        *,
        version: str = "v1",
        notes: str = "",
    ) -> StyleReferenceSet:
        if not 1 <= len(reference_ids) <= 12:
            raise ValidationError("Style reference set should contain 1–12 images (prefer 3–8)")
        for rid in reference_ids:
            ref = self.get(rid)
            if not ref:
                raise ValidationError(f"Unknown reference {rid}")
            if not Path(ref.file).is_file():
                raise ValidationError(f"Reference file missing for {rid}")
        existing = self.get_set(set_id)
        if existing and existing.status == CanonStatus.APPROVED:
            raise ValidationError(
                f"Set {set_id} is APPROVED — create a new set_id/version instead of overwrite"
            )
        s = StyleReferenceSet(
            set_id=set_id,
            series_id=self.series_id,
            version=version,
            reference_ids=list(reference_ids),
            status=CanonStatus.CANDIDATE,
            notes=notes,
            created_at=existing.created_at if existing else utcnow().isoformat(),
            updated_at=utcnow().isoformat(),
        )
        data = self._load_sets()
        data.setdefault("sets", {})[set_id] = s.model_dump(mode="json")
        self._save_sets(data)
        return s

    def get_set(self, set_id: str) -> StyleReferenceSet | None:
        raw = self._load_sets().get("sets", {}).get(set_id)
        return StyleReferenceSet.model_validate(raw) if raw else None

    def list_sets(self) -> list[StyleReferenceSet]:
        return sorted(
            [StyleReferenceSet.model_validate(v) for v in self._load_sets().get("sets", {}).values()],
            key=lambda s: s.created_at,
        )

    def approve_set(self, set_id: str) -> StyleReferenceSet:
        s = self.get_set(set_id)
        if not s:
            raise ValidationError(f"Unknown set {set_id}")
        if not (3 <= len(s.reference_ids) <= 8):
            # Prefer 3–8 but allow approve with warning note if 1–2 for bootstrapping
            if len(s.reference_ids) < 1:
                raise ValidationError("Set has no references")
        for rid in s.reference_ids:
            ref = self.get(rid)
            if not ref or ref.status != CanonStatus.APPROVED:
                raise ValidationError(
                    f"All set members must be APPROVED first (blocked: {rid})",
                )
        s.status = CanonStatus.APPROVED
        s.updated_at = utcnow().isoformat()
        data = self._load_sets()
        data["sets"][set_id] = s.model_dump(mode="json")
        self._save_sets(data)
        return s

    def style_recovery_gate(self) -> dict[str, Any]:
        """Report whether style recovery can run."""
        style_refs = self.list_references(reference_type=VisualReferenceType.STYLE_REFERENCE)
        approved_refs = [r for r in style_refs if r.status == CanonStatus.APPROVED]
        sets = self.list_sets()
        approved_sets = [s for s in sets if s.status == CanonStatus.APPROVED]
        ready = bool(approved_sets) and any(len(s.reference_ids) >= 1 for s in approved_sets)
        return {
            "ready": ready,
            "stop": None if ready else "AWAITING_STYLE_REFERENCE_IMPORT",
            "style_reference_count": len(style_refs),
            "approved_style_reference_count": len(approved_refs),
            "approved_sets": [s.set_id for s in approved_sets],
            "import_folder": str(self.imports_dir),
            "ui_action": "Streamlit → References → Import Visual Reference → create/approve set",
            "preferred_set_id": "likkle-jay-style-reference-set-v1",
        }
