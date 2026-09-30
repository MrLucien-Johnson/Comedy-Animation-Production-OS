#!/usr/bin/env python3
"""Import established Likkle Jay images from the project-root drop folder.

Default folder (Windows example):
  D:\\Apps\\comedy-animation-production-os\\Comedy-Animation-Production-OS\\visual_references

Copies into series/likkle-jay/visual_references/imports/ (never overwrites).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from capos.core.paths import project_root
from capos.core.status import VisualReferenceType
from capos.production.storage import ensure_production_tree
from capos.references.ingestion import VisualReferenceStore, style_reference_drop_folder


def main() -> int:
    parser = argparse.ArgumentParser(description="Import style references from drop folder")
    parser.add_argument(
        "--folder",
        default=None,
        help="Folder with PNG/JPG/WEBP (default: <project>/visual_references)",
    )
    parser.add_argument(
        "--approve",
        action="store_true",
        help="Mark each imported reference APPROVED",
    )
    parser.add_argument(
        "--approve-set",
        action="store_true",
        help="Create/approve likkle-jay-style-reference-set-v1 after import",
    )
    parser.add_argument(
        "--set-id",
        default="likkle-jay-style-reference-set-v1",
        help="Style reference set id",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Only list images found in the drop folder",
    )
    args = parser.parse_args()

    ensure_production_tree("likkle-jay")
    store = VisualReferenceStore("likkle-jay")
    drop = Path(args.folder) if args.folder else style_reference_drop_folder()
    drop.mkdir(parents=True, exist_ok=True)

    if args.list_only:
        files = store.list_drop_folder_images(drop)
        report = {
            "drop_folder": str(drop),
            "project_root": str(project_root()),
            "count": len(files),
            "images": [str(p) for p in files],
            "gate": store.style_recovery_gate(),
        }
        print(json.dumps(report, indent=2))
        return 0 if files else 2

    result = store.import_from_folder(
        drop,
        reference_type=VisualReferenceType.STYLE_REFERENCE,
        approve=args.approve,
        set_id=args.set_id,
        approve_set=args.approve_set,
    )
    print(json.dumps(result, indent=2))
    if result["imported_count"] == 0 and result["found"] == 0:
        print(
            "\nNo images found.\n"
            f"Put 3–8 established Likkle Jay PNG/JPG/WEBP files in:\n  {drop}\n"
            "Then re-run with: python scripts/phase2b_import_style_references.py "
            "--approve --approve-set"
        )
        return 2
    if result.get("gate", {}).get("ready"):
        print("\nGate READY — next: python scripts/phase2b_style_recovery_generate.py")
        return 0
    print("\nGate still blocked — approve references/set if needed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
