"""references package — canonical registry + visual reference ingestion."""

from capos.references.derived_crop import (
    CropBox,
    character_isolation_gate,
    create_derived_character_crop,
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
    "CropBox",
    "ReferenceStore",
    "StyleReferenceSet",
    "VisualReference",
    "VisualReferenceStore",
    "character_isolation_gate",
    "create_derived_character_crop",
    "find_likkle_jay_sheet_reference",
    "style_reference_drop_folder",
]
