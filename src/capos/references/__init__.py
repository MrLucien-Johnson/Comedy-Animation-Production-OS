"""references package — canonical registry + visual reference ingestion."""

from capos.references.crop_coords import (
    COORDINATE_MISMATCH_CAUSE,
    compute_display_scale,
    map_display_box_to_original,
)
from capos.references.derived_crop import (
    CropBox,
    character_isolation_gate,
    create_derived_character_crop,
    delete_candidate_derived,
    find_likkle_jay_sheet_reference,
)
from capos.references.ingestion import (
    StyleReferenceSet,
    VisualReference,
    VisualReferenceStore,
    style_reference_drop_folder,
)
from capos.references.versioning import ReferenceStore

__all__ = [
    "COORDINATE_MISMATCH_CAUSE",
    "CropBox",
    "ReferenceStore",
    "StyleReferenceSet",
    "VisualReference",
    "VisualReferenceStore",
    "character_isolation_gate",
    "compute_display_scale",
    "create_derived_character_crop",
    "delete_candidate_derived",
    "find_likkle_jay_sheet_reference",
    "map_display_box_to_original",
    "style_reference_drop_folder",
]
