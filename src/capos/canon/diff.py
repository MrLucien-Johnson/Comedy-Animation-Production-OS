"""COMPARE TO CANON — candidate vs approved parent/reference."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from capos.core.schemas import CanonicalAssetRef
from capos.core.status import CanonStatus, QAResultStatus, VisualReferenceType
from capos.qa.visual import (
    average_hash,
    palette_check,
    perceptual_similarity_check,
)
from capos.references.ingestion import VisualReferenceStore
from capos.references.versioning import ReferenceStore
from capos.scale.system import load_scale
from capos.spatial.layout import load_location_space


HUMAN_STYLE_REVIEW_CATEGORIES = (
    "LINEWORK_MATCH",
    "SHAPE_LANGUAGE_MATCH",
    "COLOUR_LANGUAGE_MATCH",
    "SHADING_MATCH",
    "FACE_STYLE_MATCH",
    "BACKGROUND_STYLE_MATCH",
    "COMEDY_EXPRESSIVENESS",
    "ANIME_DRIFT",
    "PHOTOREALISM_DRIFT",
    "OVER_DETAILING",
    "OVERALL_CONTINUITY",
)


def compare_to_canon(
    *,
    series_id: str,
    candidate_file: str | Path | None,
    parent_asset_id: str | None,
    candidate_metadata: dict[str, Any] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    store = ReferenceStore(series_id, root=root)
    parent: CanonicalAssetRef | None = store.get(parent_asset_id) if parent_asset_id else None
    result: dict[str, Any] = {
        "candidate_file": str(candidate_file) if candidate_file else None,
        "parent_asset_id": parent_asset_id,
        "parent_file": parent.effective_path if parent else None,
        "parent_status": (
            parent.status.value if parent and hasattr(parent.status, "value") else None
        ),
        "metadata_diff": {},
        "scale_notes": [],
        "spatial_notes": [],
        "image_similarity": None,
        "palette": None,
        "identity_claim": False,
        "review_required": True,
    }
    cand_meta = candidate_metadata or {}
    if parent:
        parent_meta = parent.metadata or {}
        keys = set(cand_meta) | set(parent_meta)
        diffs = {}
        for k in sorted(keys):
            if cand_meta.get(k) != parent_meta.get(k):
                diffs[k] = {"candidate": cand_meta.get(k), "parent": parent_meta.get(k)}
        result["metadata_diff"] = diffs
        result["parent_locked_traits"] = parent.locked_traits

    try:
        scale = load_scale(series_id, root=root)
        result["scale_notes"] = [f"{u.name}={u.value}×{u.relative_to}" for u in scale.units[:6]]
    except Exception as exc:  # noqa: BLE001
        result["scale_notes"] = [f"scale unavailable: {exc}"]

    if parent and parent.kind == "location":
        try:
            space = load_location_space(series_id, parent.slug, root=root)
            result["spatial_notes"] = [r.region_id for r in space.regions]
        except Exception as exc:  # noqa: BLE001
            result["spatial_notes"] = [str(exc)]

    if candidate_file and parent and parent.effective_path:
        sim = perceptual_similarity_check(Path(candidate_file), Path(parent.effective_path))
        result["image_similarity"] = {
            "status": sim.status.value,
            "message": sim.message,
            "details": sim.details,
        }
        pal = palette_check(Path(candidate_file), Path(parent.effective_path))
        result["palette"] = {
            "status": pal.status.value,
            "message": pal.message,
            "details": pal.details,
        }
    elif candidate_file and Path(candidate_file).is_file():
        result["image_similarity"] = {
            "status": QAResultStatus.NOT_CHECKED.value,
            "message": "No parent image file to compare",
            "candidate_hash": average_hash(Path(candidate_file)),
        }

    result["identity_claim"] = False
    result["review_required"] = True
    return result


def compare_to_reference(
    *,
    series_id: str,
    candidate_file: str | Path | None,
    reference_id: str | None = None,
    reference_set_id: str | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """Side-by-side style recovery compare — human review authoritative; no fake identity score."""
    vstore = VisualReferenceStore(series_id, root=root)
    references: list[dict[str, Any]] = []
    if reference_id:
        ref = vstore.get(reference_id)
        if ref:
            references.append(ref.model_dump(mode="json"))
    elif reference_set_id:
        s = vstore.get_set(reference_set_id)
        if s:
            for rid in s.reference_ids:
                ref = vstore.get(rid)
                if ref:
                    references.append(ref.model_dump(mode="json"))
    else:
        for ref in vstore.list_references(reference_type=VisualReferenceType.STYLE_REFERENCE):
            if ref.status == CanonStatus.APPROVED:
                references.append(ref.model_dump(mode="json"))

    result: dict[str, Any] = {
        "candidate_file": str(candidate_file) if candidate_file else None,
        "reference_id": reference_id,
        "reference_set_id": reference_set_id,
        "references": references,
        "comparisons": [],
        "human_review_categories": list(HUMAN_STYLE_REVIEW_CATEGORIES),
        "identity_claim": False,
        "semantic_identity_score": None,
        "review_required": True,
        "note": "Human review is authoritative — no automatic style pass/fail.",
    }
    if not candidate_file or not Path(candidate_file).is_file():
        result["error"] = "Candidate file missing"
        return result

    for ref in references:
        rpath = ref.get("file")
        entry: dict[str, Any] = {
            "reference_id": ref.get("reference_id"),
            "reference_file": rpath,
            "checksum": ref.get("checksum"),
            "image_similarity": None,
            "palette": None,
        }
        if rpath and Path(rpath).is_file():
            sim = perceptual_similarity_check(Path(candidate_file), Path(rpath))
            entry["image_similarity"] = {
                "status": sim.status.value,
                "message": sim.message,
                "details": sim.details,
            }
            pal = palette_check(Path(candidate_file), Path(rpath))
            entry["palette"] = {
                "status": pal.status.value,
                "message": pal.message,
                "details": pal.details,
            }
        result["comparisons"].append(entry)
    return result
