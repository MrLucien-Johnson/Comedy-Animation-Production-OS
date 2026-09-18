"""Extended canonical registry — production asset types and workflows."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from capos.core.errors import ValidationError
from capos.core.paths import series_dir
from capos.core.schemas import CanonicalAssetRef, utcnow
from capos.core.status import CanonicalAssetType, CanonStatus, StageStatus


def asset_id_for(kind: str, slug: str, version: int = 1) -> str:
    return f"{kind}-{slug}-v{version}"


def _status_value(status: StageStatus | CanonStatus | str) -> str:
    return status.value if hasattr(status, "value") else str(status)


def _is_protected(status: StageStatus | CanonStatus | str) -> bool:
    return _status_value(status) in {
        CanonStatus.APPROVED.value,
        StageStatus.APPROVED.value,
        StageStatus.LOCKED.value,
    }


class ReferenceStore:
    """Manage versioned canonical assets for a series."""

    def __init__(self, series_id: str, *, root: Path | None = None) -> None:
        self.series_id = series_id
        self.root = root
        self.base = series_dir(series_id, root=root)
        self.index_path = self.base / "references" / "canonical_index.json"

    def _load_index(self) -> dict[str, Any]:
        if not self.index_path.is_file():
            return {"assets": {}}
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def _save_index(self, data: dict[str, Any]) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    def _persist(self, ref: CanonicalAssetRef) -> CanonicalAssetRef:
        data = self._load_index()
        data.setdefault("assets", {})[ref.asset_id] = ref.model_dump(mode="json")
        self._save_index(data)
        return ref

    def get(self, asset_id: str) -> CanonicalAssetRef | None:
        assets = self._load_index().get("assets", {})
        raw = assets.get(asset_id)
        return CanonicalAssetRef.model_validate(raw) if raw else None

    def list_assets(
        self,
        *,
        kind: str | None = None,
        asset_type: CanonicalAssetType | str | None = None,
        status: str | None = None,
    ) -> list[CanonicalAssetRef]:
        assets = self._load_index().get("assets", {})
        out = [CanonicalAssetRef.model_validate(v) for v in assets.values()]
        if kind:
            out = [a for a in out if a.kind == kind]
        if asset_type:
            t = asset_type.value if hasattr(asset_type, "value") else str(asset_type)
            out = [a for a in out if a.type and _status_value(a.type) == t]
        if status:
            out = [a for a in out if _status_value(a.status) == status]
        return sorted(out, key=lambda a: a.asset_id)

    def register(
        self, ref: CanonicalAssetRef, *, allow_replace_draft: bool = True
    ) -> CanonicalAssetRef:
        if not ref.series_id:
            ref.series_id = self.series_id
        data = self._load_index()
        assets: dict[str, Any] = data.setdefault("assets", {})
        existing = assets.get(ref.asset_id)
        if existing:
            prev = CanonicalAssetRef.model_validate(existing)
            if _is_protected(prev.status):
                raise ValidationError(
                    f"Cannot overwrite approved/locked canonical asset {ref.asset_id}",
                    hint="Call create_new_version() instead.",
                )
            prev_status = _status_value(prev.status)
            updatable = {
                CanonStatus.DRAFT.value,
                StageStatus.DRAFT.value,
                CanonStatus.REFERENCE_REQUIRED.value,
                CanonStatus.CANDIDATE.value,
                CanonStatus.REVIEW_REQUIRED.value,
                CanonStatus.REJECTED.value,
            }
            if prev_status not in updatable or not allow_replace_draft:
                raise ValidationError(
                    f"Asset {ref.asset_id} already exists with status {prev.status}"
                )
        ref.updated_at = utcnow()
        assets[ref.asset_id] = ref.model_dump(mode="json")
        self._save_index(data)
        return ref

    def mark_candidate(self, asset_id: str) -> CanonicalAssetRef:
        ref = self.get(asset_id)
        if not ref:
            raise ValidationError(f"Unknown asset {asset_id}")
        if not ref.effective_path or not Path(ref.effective_path).is_file():
            raise ValidationError(
                f"Asset {asset_id} has no image file — cannot mark CANDIDATE",
                hint="Generate or import an image first. Do not claim assets exist without files.",
            )
        ref.status = CanonStatus.CANDIDATE
        ref.updated_at = utcnow()
        return self._persist(ref)

    def mark_review_required(self, asset_id: str, reason: str = "") -> CanonicalAssetRef:
        ref = self.get(asset_id)
        if not ref:
            raise ValidationError(f"Unknown asset {asset_id}")
        ref.status = CanonStatus.REVIEW_REQUIRED
        if reason:
            ref.metadata = {**ref.metadata, "review_reason": reason}
        ref.updated_at = utcnow()
        return self._persist(ref)

    def mark_reference_required(self, asset_id: str, reason: str) -> CanonicalAssetRef:
        ref = self.get(asset_id)
        if not ref:
            raise ValidationError(f"Unknown asset {asset_id}")
        ref.status = CanonStatus.REFERENCE_REQUIRED
        ref.reference_required = True
        ref.reference_required_reason = reason
        ref.source = "reference_required"
        ref.updated_at = utcnow()
        return self._persist(ref)

    def attach_file(
        self,
        asset_id: str,
        file_path: str | Path,
        *,
        source: str = "imported",
    ) -> CanonicalAssetRef:
        ref = self.get(asset_id)
        if not ref:
            raise ValidationError(f"Unknown asset {asset_id}")
        path = Path(file_path)
        if not path.is_file():
            raise ValidationError(f"Image file missing: {path}")
        if _is_protected(ref.status):
            raise ValidationError(
                f"Cannot replace file on approved asset {asset_id}",
                hint="create_new_version() then attach_file on the new version.",
            )
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        ref.file = str(path)
        ref.path = str(path)
        ref.checksum = checksum
        ref.source = source
        ref.reference_required = False
        ref.status = CanonStatus.CANDIDATE
        ref.updated_at = utcnow()
        return self._persist(ref)

    def approve(self, asset_id: str, *, require_file: bool = True) -> CanonicalAssetRef:
        """Approve for production lock. Requires an actual image file by default."""
        ref = self.get(asset_id)
        if not ref:
            raise ValidationError(f"Unknown asset {asset_id}")
        if require_file and (not ref.effective_path or not Path(ref.effective_path).is_file()):
            raise ValidationError(
                f"Cannot APPROVE {asset_id} without an image file",
                hint="Attach/generate a real image first. Metadata-only assets stay DRAFT.",
            )
        ref.status = CanonStatus.APPROVED
        ref.approved_at = utcnow()
        ref.updated_at = utcnow()
        return self._persist(ref)

    def reject(self, asset_id: str, reason: str = "") -> CanonicalAssetRef:
        ref = self.get(asset_id)
        if not ref:
            raise ValidationError(f"Unknown asset {asset_id}")
        if _status_value(ref.status) == StageStatus.LOCKED.value:
            raise ValidationError(f"Cannot reject LOCKED asset {asset_id}")
        ref.status = CanonStatus.REJECTED
        if reason:
            ref.metadata = {**ref.metadata, "reject_reason": reason}
        ref.updated_at = utcnow()
        return self._persist(ref)

    def lock_as_canon(self, asset_id: str) -> CanonicalAssetRef:
        ref = self.get(asset_id)
        if not ref:
            raise ValidationError(f"Unknown asset {asset_id}")
        if not ref.is_production_lockable():
            raise ValidationError(
                f"Asset {asset_id} status {ref.status} cannot lock",
                hint="Approve the asset with an image file first.",
            )
        if not ref.effective_path or not Path(ref.effective_path).is_file():
            raise ValidationError(f"Cannot lock {asset_id} — image file missing")
        ref.status = StageStatus.LOCKED
        ref.updated_at = utcnow()
        return self._persist(ref)

    def create_new_version(
        self,
        asset_id: str,
        *,
        path: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CanonicalAssetRef:
        prev = self.get(asset_id)
        if not prev:
            raise ValidationError(f"Unknown asset {asset_id}")
        new_version = prev.version + 1
        kind_for_id = prev.kind
        new_id = asset_id_for(kind_for_id, prev.slug, new_version)
        if self.get(new_id):
            raise ValidationError(f"Next version already exists: {new_id}")

        new_ref = CanonicalAssetRef(
            asset_id=new_id,
            type=prev.type,
            kind=prev.kind,
            series_id=prev.series_id or self.series_id,
            slug=prev.slug,
            version=new_version,
            status=CanonStatus.DRAFT,
            path=path,
            file=path,
            locked_traits=list(prev.locked_traits),
            metadata={**(prev.metadata or {}), **(metadata or {})},
            supersedes=prev.asset_id,
        )
        prev.status = CanonStatus.SUPERSEDED
        prev.superseded_by = new_id
        prev.updated_at = utcnow()
        data = self._load_index()
        data["assets"][prev.asset_id] = prev.model_dump(mode="json")
        data["assets"][new_id] = new_ref.model_dump(mode="json")
        self._save_index(data)
        return new_ref

    def resolve_governing_refs(self, frame_refs: dict[str, Any]) -> dict[str, CanonicalAssetRef]:
        out: dict[str, CanonicalAssetRef] = {}
        for key, asset_id in frame_refs.items():
            if asset_id is None:
                continue
            if isinstance(asset_id, list):
                for i, aid in enumerate(asset_id):
                    ref = self.get(aid)
                    if not ref:
                        raise ValidationError(f"Missing canonical asset {aid} for {key}[{i}]")
                    out[f"{key}:{aid}"] = ref
            else:
                ref = self.get(asset_id)
                if not ref:
                    raise ValidationError(f"Missing canonical asset {asset_id} for {key}")
                out[key] = ref
        return out

    def production_locks(self) -> list[CanonicalAssetRef]:
        """Assets eligible to govern generation (APPROVED/LOCKED with files)."""
        out = []
        for a in self.list_assets():
            status = _status_value(a.status)
            if (
                status in {CanonStatus.APPROVED.value, StageStatus.LOCKED.value}
                and a.has_image_file()
            ):
                out.append(a)
        return out
