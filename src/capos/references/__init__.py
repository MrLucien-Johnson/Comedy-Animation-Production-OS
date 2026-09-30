"""references package — canonical registry + visual reference ingestion."""

from capos.references.ingestion import (
    StyleReferenceSet,
    VisualReference,
    VisualReferenceStore,
    style_reference_drop_folder,
)
from capos.references.versioning import ReferenceStore

__all__ = [
    "ReferenceStore",
    "StyleReferenceSet",
    "VisualReference",
    "VisualReferenceStore",
    "style_reference_drop_folder",
]
