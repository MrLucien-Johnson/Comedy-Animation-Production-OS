"""Bootstrap Likkle Jay production canon registry (metadata + REFERENCE_REQUIRED).

Does NOT create or claim image files.
"""

from __future__ import annotations

from pathlib import Path

from capos.core.schemas import CanonicalAssetRef
from capos.core.status import CanonicalAssetType, CanonStatus
from capos.references.golden import GoldenFrameStore
from capos.references.versioning import ReferenceStore
from capos.scale.system import LIKKLE_JAY_DEFAULT_SCALE, save_scale
from capos.spatial.layout import write_default_spaces

TURNAROUNDS = [
    ("front", "FRONT"),
    ("three-quarter-left", "3/4 LEFT"),
    ("three-quarter-right", "3/4 RIGHT"),
    ("side-left", "SIDE LEFT"),
    ("side-right", "SIDE RIGHT"),
    ("back", "BACK"),
]

JAY_EXPRESSIONS = [
    "NEUTRAL",
    "HAPPY",
    "MISCHIEVOUS",
    "EXCITED",
    "SURPRISED",
    "SHOCKED",
    "GUILTY",
    "NERVOUS",
    "INNOCENT_DENIAL",
    "LAUGHING",
]

BEV_EXPRESSIONS = [
    "NEUTRAL",
    "SUSPICIOUS",
    "CONFUSED",
    "STERN",
    "ANNOYED",
    "SHOCKED",
    "SCOLDING",
    "AMUSED",
]

COOKIE_STATES = [
    "CLOSED",
    "OPEN_LID_RIGHT",
    "OPEN_LID_LEFT",
    "PARTIALLY_FULL",
    "EMPTY",
]


def _ensure(
    store: ReferenceStore,
    *,
    asset_id: str,
    kind: str,
    slug: str,
    asset_type: CanonicalAssetType,
    locked_traits: list[str],
    metadata: dict | None = None,
    status: CanonStatus = CanonStatus.DRAFT,
) -> CanonicalAssetRef:
    existing = store.get(asset_id)
    if existing:
        # Upgrade type/metadata without claiming files
        if existing.type is None:
            existing.type = asset_type
        existing.series_id = store.series_id
        existing.locked_traits = locked_traits or existing.locked_traits
        if metadata:
            existing.metadata = {**existing.metadata, **metadata}
        if existing.effective_path is None and status == CanonStatus.REFERENCE_REQUIRED:
            existing.status = CanonStatus.REFERENCE_REQUIRED
            existing.reference_required = True
        return store.register(existing, allow_replace_draft=True)

    return store.register(
        CanonicalAssetRef(
            asset_id=asset_id,
            type=asset_type,
            kind=kind,
            series_id=store.series_id,
            slug=slug,
            version=1,
            status=status,
            source="registry",
            locked_traits=locked_traits,
            metadata=metadata or {},
            reference_required=(status == CanonStatus.REFERENCE_REQUIRED),
            reference_required_reason=(
                "No production image file yet — generate or import before APPROVED"
                if status == CanonStatus.REFERENCE_REQUIRED
                else None
            ),
        )
    )


def bootstrap_likkle_jay_canon(*, root: Path | None = None) -> dict:
    series_id = "likkle-jay"
    store = ReferenceStore(series_id, root=root)
    created: list[str] = []

    masters = [
        (
            "character-likkle-jay-v1",
            "character",
            "likkle-jay",
            CanonicalAssetType.CHARACTER_MASTER,
            [
                "hair:rounded dome of tight black curls, full and consistent",
                "skin:medium/dark brown",
                "face:round youthful cheeks",
                "wardrobe:yellow T-shirt red collar green shorts",
            ],
            {
                "hair_hard_lock": "rounded dome of tight black curls, full and consistent",
                "prohibited_hair": [
                    "fade",
                    "taper",
                    "crop",
                    "flat top",
                    "slick",
                    "straight",
                    "loose curls",
                    "different length",
                ],
            },
        ),
        (
            "character-auntie-bev-v1",
            "character",
            "auntie-bev",
            CanonicalAssetType.CHARACTER_MASTER,
            [
                "silhouette:rounded/stout",
                "floral house dress",
                "matching headwrap",
                "round glasses",
                "gold earrings",
            ],
            {"prop_when_scolding": "wooden spoon"},
        ),
        (
            "outfit-likkle-jay-default-v1",
            "outfit",
            "likkle-jay-default",
            CanonicalAssetType.OUTFIT_MASTER,
            ["yellow T-shirt", "red collar trim", "green shorts"],
            {},
        ),
        (
            "outfit-auntie-bev-default-v1",
            "outfit",
            "auntie-bev-default",
            CanonicalAssetType.OUTFIT_MASTER,
            ["orange/red floral house dress", "matching headwrap"],
            {},
        ),
        (
            "location-kitchen-v1",
            "location",
            "kitchen",
            CanonicalAssetType.LOCATION_MASTER,
            ["counter left", "fridge right", "straight-on camera", "no mirror"],
            {"prop_default_region": {"cookie-jar": "LEFT_COUNTER"}},
        ),
        (
            "location-living-room-v1",
            "location",
            "living-room",
            CanonicalAssetType.LOCATION_MASTER,
            ["sofa placement", "window side"],
            {},
        ),
        (
            "location-yard-v1",
            "location",
            "yard",
            CanonicalAssetType.LOCATION_MASTER,
            ["fence line", "house exterior side"],
            {},
        ),
        (
            "location-jay-bedroom-v1",
            "location",
            "jay-bedroom",
            CanonicalAssetType.LOCATION_MASTER,
            ["bed side", "window placement"],
            {},
        ),
        (
            "prop-cookie-jar-v1",
            "prop",
            "cookie-jar",
            CanonicalAssetType.PROP_MASTER,
            ["label:COOKIES", "glass jar", "rounded lid", "small cookies"],
            {
                "label": "COOKIES",
                "states": COOKIE_STATES,
                "default_region": "LEFT_COUNTER",
            },
        ),
        (
            "style-likkle-jay-v1",
            "style",
            "likkle-jay",
            CanonicalAssetType.STYLE_MASTER,
            [
                "warm-toned family-friendly fictional 2D cartoon",
                "bold dark outlines",
                "flat shading",
                "1:1 master",
            ],
            {"watermark": "MRLUCIENJOHNSON"},
        ),
    ]
    for asset_id, kind, slug, atype, traits, meta in masters:
        _ensure(
            store,
            asset_id=asset_id,
            kind=kind,
            slug=slug,
            asset_type=atype,
            locked_traits=traits,
            metadata=meta,
            status=CanonStatus.REFERENCE_REQUIRED,
        )
        created.append(asset_id)

    for slug_suffix, label in TURNAROUNDS:
        aid = f"turnaround-likkle-jay-{slug_suffix}-v1"
        _ensure(
            store,
            asset_id=aid,
            kind="turnaround",
            slug=f"likkle-jay-{slug_suffix}",
            asset_type=CanonicalAssetType.CHARACTER_TURNAROUND,
            locked_traits=["inherits character-likkle-jay-v1 hair+outfit locks"],
            metadata={"view": label, "character_id": "likkle-jay"},
            status=CanonStatus.REFERENCE_REQUIRED,
        )
        created.append(aid)
        # Auntie Bev turnarounds (front + 3/4 + side + back subset)
        if slug_suffix in {"front", "three-quarter-left", "side-left", "back"}:
            baid = f"turnaround-auntie-bev-{slug_suffix}-v1"
            _ensure(
                store,
                asset_id=baid,
                kind="turnaround",
                slug=f"auntie-bev-{slug_suffix}",
                asset_type=CanonicalAssetType.CHARACTER_TURNAROUND,
                locked_traits=["inherits character-auntie-bev-v1 locks"],
                metadata={"view": label, "character_id": "auntie-bev"},
                status=CanonStatus.REFERENCE_REQUIRED,
            )
            created.append(baid)

    for expr in JAY_EXPRESSIONS:
        slug = expr.lower().replace("_", "-")
        aid = f"expression-likkle-jay-{slug}-v1"
        _ensure(
            store,
            asset_id=aid,
            kind="expression",
            slug=f"likkle-jay-{slug}",
            asset_type=CanonicalAssetType.CHARACTER_EXPRESSION,
            locked_traits=["facial acting only — do not redefine hair/outfit/identity"],
            metadata={"expression": expr, "character_id": "likkle-jay"},
            status=CanonStatus.REFERENCE_REQUIRED,
        )
        created.append(aid)

    for expr in BEV_EXPRESSIONS:
        slug = expr.lower().replace("_", "-")
        aid = f"expression-auntie-bev-{slug}-v1"
        _ensure(
            store,
            asset_id=aid,
            kind="expression",
            slug=f"auntie-bev-{slug}",
            asset_type=CanonicalAssetType.CHARACTER_EXPRESSION,
            locked_traits=["facial acting only — do not redefine identity"],
            metadata={"expression": expr, "character_id": "auntie-bev"},
            status=CanonStatus.REFERENCE_REQUIRED,
        )
        created.append(aid)

    for state in COOKIE_STATES:
        slug = state.lower().replace("_", "-")
        aid = f"prop-state-cookie-jar-{slug}-v1"
        _ensure(
            store,
            asset_id=aid,
            kind="prop-state",
            slug=f"cookie-jar-{slug}",
            asset_type=CanonicalAssetType.PROP_STATE,
            locked_traits=["identity=prop-cookie-jar-v1", "label:COOKIES"],
            metadata={"prop_id": "cookie-jar", "state": state, "label": "COOKIES"},
            status=CanonStatus.REFERENCE_REQUIRED,
        )
        created.append(aid)

    # Kitchen camera + prop layout assets
    _ensure(
        store,
        asset_id="location-camera-kitchen-v1",
        kind="location-camera",
        slug="kitchen-camera",
        asset_type=CanonicalAssetType.LOCATION_CAMERA,
        locked_traits=["straight-on baseline", "do not mirror"],
        metadata={"location_id": "kitchen"},
        status=CanonStatus.REFERENCE_REQUIRED,
    )
    created.append("location-camera-kitchen-v1")
    _ensure(
        store,
        asset_id="location-prop-layout-kitchen-v1",
        kind="location-prop-layout",
        slug="kitchen-prop-layout",
        asset_type=CanonicalAssetType.LOCATION_PROP_LAYOUT,
        locked_traits=["cookie-jar→LEFT_COUNTER", "fridge→RIGHT_FRIDGE"],
        metadata={"location_id": "kitchen"},
        status=CanonStatus.REFERENCE_REQUIRED,
    )
    created.append("location-prop-layout-kitchen-v1")

    save_scale(LIKKLE_JAY_DEFAULT_SCALE, root=root)
    write_default_spaces(series_id, root=root)
    golden = GoldenFrameStore(series_id, root=root)
    g = golden.ensure_s01e02_open_jar_placeholder()

    return {
        "series_id": series_id,
        "registry_entries": sorted(set(created)),
        "images_created": 0,
        "images_claimed": False,
        "golden_reference_required": g.golden_id,
        "note": (
            "Canon registry bootstrapped as REFERENCE_REQUIRED / DRAFT metadata only. "
            "No production images were generated or claimed."
        ),
    }
