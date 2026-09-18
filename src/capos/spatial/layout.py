"""Spatial continuity — normalized location regions for prop/camera locks."""

from __future__ import annotations

import json
from pathlib import Path

from capos.core.errors import ValidationError
from capos.core.paths import series_dir
from capos.core.schemas import LocationSpace, SpatialRegion


def _kitchen_space(series_id: str = "likkle-jay") -> LocationSpace:
    return LocationSpace(
        location_id="kitchen",
        series_id=series_id,
        camera_baseline="straight-on cartoon baseline; do not mirror",
        immutable_geometry=[
            "wall geometry",
            "counter on LEFT",
            "refrigerator on RIGHT",
            "cabinet style with round handles",
            "floor tile family",
            "camera baseline",
        ],
        allowed_movable=["cookie-jar", "wooden-spoon", "small-dishes"],
        palette=[
            "warm beige/orange walls",
            "terracotta/brown floor",
            "wood cabinets",
            "cream fridge",
        ],
        lighting="warm indoor kitchen daylight",
        regions=[
            SpatialRegion(
                region_id="LEFT_COUNTER",
                label="Counter surface on LEFT",
                x=0.05,
                y=0.45,
                w=0.40,
                h=0.25,
                locked=True,
                notes="Cookie jar default region",
            ),
            SpatialRegion(
                region_id="RIGHT_FRIDGE",
                label="Cream refrigerator RIGHT edge",
                x=0.70,
                y=0.15,
                w=0.25,
                h=0.70,
                locked=True,
            ),
            SpatialRegion(
                region_id="CABINETS_UPPER",
                label="Upper wooden cabinets",
                x=0.05,
                y=0.05,
                w=0.60,
                h=0.25,
                locked=True,
            ),
            SpatialRegion(
                region_id="FLOOR",
                label="Terracotta/brown tiled floor",
                x=0.0,
                y=0.75,
                w=1.0,
                h=0.25,
                locked=True,
            ),
            SpatialRegion(
                region_id="LID_BESIDE_JAR",
                label="Lid placement beside jar when OPEN",
                x=0.28,
                y=0.48,
                w=0.12,
                h=0.10,
                locked=False,
                notes="Used for OPEN_LID_RIGHT / OPEN_LID_LEFT episode states",
            ),
        ],
    )


def _living_room_space(series_id: str = "likkle-jay") -> LocationSpace:
    return LocationSpace(
        location_id="living-room",
        series_id=series_id,
        camera_baseline="straight-on medium establishing",
        immutable_geometry=["sofa placement", "window side", "overall palette"],
        allowed_movable=["remote", "cushion", "small-toys"],
        palette=["warm neutrals", "soft accent cushions"],
        lighting="soft daylight",
        regions=[
            SpatialRegion(
                region_id="SOFA", label="Sofa", x=0.2, y=0.45, w=0.55, h=0.30, locked=True
            ),
            SpatialRegion(
                region_id="WINDOW", label="Window", x=0.65, y=0.1, w=0.25, h=0.35, locked=True
            ),
        ],
    )


def _yard_space(series_id: str = "likkle-jay") -> LocationSpace:
    return LocationSpace(
        location_id="yard",
        series_id=series_id,
        camera_baseline="straight-on exterior baseline",
        immutable_geometry=["fence line", "house exterior side"],
        allowed_movable=["hose", "bucket", "toys"],
        palette=["green grass", "warm sky", "wooden fence"],
        lighting="warm daylight",
        regions=[
            SpatialRegion(
                region_id="LAWN", label="Grass lawn", x=0.1, y=0.5, w=0.8, h=0.4, locked=True
            ),
            SpatialRegion(
                region_id="FENCE", label="Fence line", x=0.0, y=0.25, w=1.0, h=0.2, locked=True
            ),
        ],
    )


def _bedroom_space(series_id: str = "likkle-jay") -> LocationSpace:
    return LocationSpace(
        location_id="jay-bedroom",
        series_id=series_id,
        camera_baseline="straight-on bedroom baseline",
        immutable_geometry=["bed side", "window placement"],
        allowed_movable=["toys", "blanket", "books"],
        palette=["warm soft walls", "restrained colour accents"],
        lighting="soft indoor",
        regions=[
            SpatialRegion(region_id="BED", label="Bed", x=0.15, y=0.45, w=0.5, h=0.35, locked=True),
            SpatialRegion(
                region_id="DRESSER", label="Dresser", x=0.7, y=0.4, w=0.25, h=0.35, locked=True
            ),
        ],
    )


DEFAULT_SPACES = {
    "kitchen": _kitchen_space,
    "living-room": _living_room_space,
    "yard": _yard_space,
    "jay-bedroom": _bedroom_space,
}


def space_path(series_id: str, location_id: str, *, root: Path | None = None) -> Path:
    return series_dir(series_id, root=root) / "spatial" / f"{location_id}.json"


def load_location_space(
    series_id: str, location_id: str, *, root: Path | None = None
) -> LocationSpace:
    path = space_path(series_id, location_id, root=root)
    if path.is_file():
        return LocationSpace.model_validate(json.loads(path.read_text(encoding="utf-8")))
    if location_id in DEFAULT_SPACES:
        return DEFAULT_SPACES[location_id](series_id)
    raise ValidationError(f"Unknown location space: {location_id}")


def save_location_space(space: LocationSpace, *, root: Path | None = None) -> Path:
    path = space_path(space.series_id, space.location_id, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(space.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def get_region(space: LocationSpace, region_id: str) -> SpatialRegion:
    for r in space.regions:
        if r.region_id == region_id:
            return r
    raise ValidationError(f"Region {region_id} not in {space.location_id}")


def compile_spatial_prompt_block(
    space: LocationSpace,
    *,
    prop_regions: dict[str, str] | None = None,
) -> str:
    """
    Compile locked regions into generation instructions.
    Example: cookie jar → LEFT_COUNTER (not 'somewhere on counter').
    """
    prop_regions = prop_regions or {}
    lines = [
        f"LOCATION SPACE LOCK: {space.location_id}",
        f"Camera baseline: {space.camera_baseline}",
        f"Lighting: {space.lighting}",
        "Immutable geometry: " + "; ".join(space.immutable_geometry),
        "Allowed movable only: " + ", ".join(space.allowed_movable),
        "Regions (normalized x,y,w,h 0–1):",
    ]
    for r in space.regions:
        lines.append(
            f"- {r.region_id}: x={r.x:.2f} y={r.y:.2f} w={r.w:.2f} h={r.h:.2f} "
            f"locked={r.locked} — {r.label}"
        )
    for prop_id, region_id in prop_regions.items():
        region = get_region(space, region_id)
        lines.append(
            f"PROP PLACEMENT LOCK: {prop_id} occupying locked region {region_id} "
            f"({region.label}) at normalized box "
            f"({region.x:.2f},{region.y:.2f},{region.w:.2f},{region.h:.2f}). "
            f"Do not place {prop_id} vaguely 'somewhere on counter'."
        )
    return "\n".join(lines)


def write_default_spaces(series_id: str = "likkle-jay", *, root: Path | None = None) -> list[Path]:
    paths = []
    for _loc_id, factory in DEFAULT_SPACES.items():
        paths.append(save_location_space(factory(series_id), root=root))
    return paths
