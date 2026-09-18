"""Canonical reference versioning — never silently overwrite approved assets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from capos.core.errors import ValidationError
from capos.core.paths import series_dir
from capos.core.schemas import CanonicalAssetRef, utcnow
from capos.core.status import StageStatus


def asset_id_for(kind: str, slug: str, version: int = 1) -> str:
    return f"{kind}-{slug}-v{version}"


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

    def get(self, asset_id: str) -> CanonicalAssetRef | None:
        assets = self._load_index().get("assets", {})
        raw = assets.get(asset_id)
        return CanonicalAssetRef.model_validate(raw) if raw else None

    def list_assets(self, *, kind: str | None = None) -> list[CanonicalAssetRef]:
        assets = self._load_index().get("assets", {})
        out = [CanonicalAssetRef.model_validate(v) for v in assets.values()]
        if kind:
            out = [a for a in out if a.kind == kind]
        return sorted(out, key=lambda a: a.asset_id)

    def register(
        self, ref: CanonicalAssetRef, *, allow_replace_draft: bool = True
    ) -> CanonicalAssetRef:
        data = self._load_index()
        assets: dict[str, Any] = data.setdefault("assets", {})
        existing = assets.get(ref.asset_id)
        if existing:
            prev = CanonicalAssetRef.model_validate(existing)
            if prev.status in {StageStatus.APPROVED, StageStatus.LOCKED}:
                raise ValidationError(
                    f"Cannot overwrite approved/locked canonical asset {ref.asset_id}",
                    hint="Call create_new_version() instead.",
                )
            if prev.status != StageStatus.DRAFT or not allow_replace_draft:
                raise ValidationError(
                    f"Asset {ref.asset_id} already exists with status {prev.status}"
                )
        ref.updated_at = utcnow()
        assets[ref.asset_id] = ref.model_dump(mode="json")
        self._save_index(data)
        return ref

    def lock_as_canon(self, asset_id: str) -> CanonicalAssetRef:
        ref = self.get(asset_id)
        if not ref:
            raise ValidationError(f"Unknown asset {asset_id}")
        if ref.status not in {StageStatus.APPROVED, StageStatus.GENERATED, StageStatus.QA_PASSED}:
            raise ValidationError(
                f"Asset {asset_id} status {ref.status} cannot lock",
                hint="Approve the asset first.",
            )
        ref.status = StageStatus.LOCKED
        ref.updated_at = utcnow()
        data = self._load_index()
        data["assets"][asset_id] = ref.model_dump(mode="json")
        self._save_index(data)
        return ref

    def approve(self, asset_id: str) -> CanonicalAssetRef:
        ref = self.get(asset_id)
        if not ref:
            raise ValidationError(f"Unknown asset {asset_id}")
        ref.status = StageStatus.APPROVED
        ref.updated_at = utcnow()
        data = self._load_index()
        data["assets"][asset_id] = ref.model_dump(mode="json")
        self._save_index(data)
        return ref

    def create_new_version(
        self,
        asset_id: str,
        *,
        path: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CanonicalAssetRef:
        """Supersede an approved/locked asset with a new version id."""
        prev = self.get(asset_id)
        if not prev:
            raise ValidationError(f"Unknown asset {asset_id}")
        new_version = prev.version + 1
        new_id = asset_id_for(prev.kind, prev.slug, new_version)
        if self.get(new_id):
            raise ValidationError(f"Next version already exists: {new_id}")

        new_ref = CanonicalAssetRef(
            asset_id=new_id,
            kind=prev.kind,
            slug=prev.slug,
            version=new_version,
            status=StageStatus.DRAFT,
            path=path,
            locked_traits=list(prev.locked_traits),
            metadata={**(prev.metadata or {}), **(metadata or {})},
        )
        prev.status = StageStatus.SUPERSEDED
        prev.superseded_by = new_id
        prev.updated_at = utcnow()

        data = self._load_index()
        data["assets"][prev.asset_id] = prev.model_dump(mode="json")
        data["assets"][new_id] = new_ref.model_dump(mode="json")
        self._save_index(data)
        return new_ref

    def resolve_governing_refs(self, frame_refs: dict[str, Any]) -> dict[str, CanonicalAssetRef]:
        """Map frame reference ids to canonical assets; fail if missing."""
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
