"""Production asset storage hierarchy."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from capos.core.errors import ValidationError
from capos.core.paths import project_root
from capos.core.schemas import utcnow


def production_root(series_id: str = "likkle-jay", *, root: Path | None = None) -> Path:
    return (root or project_root()) / "production" / series_id


def candidates_dir(series_id: str = "likkle-jay", *, root: Path | None = None) -> Path:
    return production_root(series_id, root=root) / "candidates"


def canon_dir(series_id: str = "likkle-jay", *, root: Path | None = None) -> Path:
    return production_root(series_id, root=root) / "canon"


def rejected_dir(series_id: str = "likkle-jay", *, root: Path | None = None) -> Path:
    return production_root(series_id, root=root) / "rejected"


def ensure_production_tree(series_id: str = "likkle-jay", *, root: Path | None = None) -> Path:
    base = production_root(series_id, root=root)
    paths = [
        base / "candidates",
        base / "rejected",
        base / "episodes",
        base / "exports",
        base / "canon" / "style",
        base / "canon" / "characters" / "likkle-jay",
        base / "canon" / "characters" / "auntie-bev",
        base / "canon" / "locations" / "kitchen",
        base / "canon" / "locations" / "living-room",
        base / "canon" / "locations" / "yard",
        base / "canon" / "locations" / "bedroom",
        base / "canon" / "props" / "cookie-jar",
        base / "canon" / "golden",
    ]
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)
        keep = p / ".gitkeep"
        if not keep.exists():
            keep.write_text("")
    return base


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def register_production_file(
    *,
    series_id: str,
    category: str,
    asset_slug: str,
    source_path: Path,
    root: Path | None = None,
    kind: str = "candidate",
) -> dict[str, Any]:
    """
    Copy an image into production storage and return checksum metadata.
    kind: candidate | canon | rejected
    """
    if not source_path.is_file():
        raise ValidationError(f"Source image missing: {source_path}")
    ensure_production_tree(series_id, root=root)
    if kind == "candidate":
        dest_dir = candidates_dir(series_id, root=root) / category / asset_slug
    elif kind == "rejected":
        dest_dir = rejected_dir(series_id, root=root) / category / asset_slug
    else:
        dest_dir = canon_dir(series_id, root=root) / category / asset_slug
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / source_path.name
    if dest.resolve() != source_path.resolve():
        shutil.copy2(source_path, dest)
    checksum = sha256_file(dest)
    meta = {
        "file": str(dest),
        "checksum": checksum,
        "category": category,
        "asset_slug": asset_slug,
        "kind": kind,
        "registered_at": utcnow().isoformat(),
        "bytes": dest.stat().st_size,
    }
    (dest_dir / f"{dest.stem}.meta.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    return meta
