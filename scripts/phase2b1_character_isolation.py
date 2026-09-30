#!/usr/bin/env python3
"""Phase 2B.1 — Character isolation from derived front crop.

1. Marks Phase 2B recovery as TECHNICAL_SUCCESS_STYLE_RECOVERY_NOT_YET_APPROVED
2. Requires approved character-likkle-jay-front-derived-v1
3. Generates exactly 3 clean standalone Likkle Jay img2img candidates (denoise 0.30/0.375/0.45)
4. Stops at AWAITING_HUMAN_CHARACTER_ISOLATION_REVIEW
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from capos.canon.pipeline import CanonCreationPipeline
from capos.canon.style_recovery_hold import mark_style_recovery_technical_success
from capos.core.status import CanonStatus
from capos.production.storage import ensure_production_tree
from capos.references.derived_crop import (
    CropBox,
    character_isolation_gate,
    create_derived_character_crop,
    find_likkle_jay_sheet_reference,
)
from capos.references.ingestion import VisualReferenceStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 2B.1 character isolation")
    parser.add_argument("--hold-only", action="store_true", help="Only mark 2B recovery hold")
    parser.add_argument(
        "--crop",
        nargs=4,
        type=int,
        metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"),
        help="Create derived crop from character-likkle-jay sheet (pixels)",
    )
    parser.add_argument("--source-id", default="character-likkle-jay-v1")
    parser.add_argument("--derived-id", default="character-likkle-jay-front-derived-v1")
    parser.add_argument("--approve-derived", action="store_true")
    parser.add_argument("--generate", action="store_true", help="Generate 3 isolation candidates")
    args = parser.parse_args()

    series_id = "likkle-jay"
    ensure_production_tree(series_id)
    os.environ.setdefault("CAPOS_COMFYUI_URL", "http://127.0.0.1:8188")
    os.environ.setdefault("CAPOS_COMFYUI_CHECKPOINT", "toonyou_beta6.safetensors")

    hold = mark_style_recovery_technical_success(series_id)
    vstore = VisualReferenceStore(series_id)
    report: dict = {
        "PHASE": "2B.1 CHARACTER ISOLATION",
        "style_recovery_hold": hold,
        "BACKEND": "COMFYUI LOCAL",
        "GPU": "RTX 3050 6GB",
        "CHECKPOINT": os.environ.get("CAPOS_COMFYUI_CHECKPOINT"),
        "CONDITIONING": "cropped character reference + controlled img2img",
        "MOCK": 0,
        "TXT2IMG_FALLBACK": "DISABLED",
    }

    if args.hold_only:
        report["CURRENT_GATE"] = hold.get("next")
        print(json.dumps(report, indent=2))
        return 0

    if args.crop:
        left, top, right, bottom = args.crop
        sheet = find_likkle_jay_sheet_reference(vstore)
        source_id = args.source_id
        if sheet:
            source_id = sheet.reference_id
        derived = create_derived_character_crop(
            vstore,
            source_reference_id=source_id,
            crop=CropBox(left, top, right, bottom),
            derived_id=args.derived_id,
        )
        if args.approve_derived:
            derived = vstore.approve_reference(derived.reference_id)
        report["DERIVED_REFERENCE_CREATED"] = derived.model_dump(mode="json")

    gate = character_isolation_gate(vstore)
    report["ORIGINAL_REFERENCE"] = gate.get("original_reference")
    report["DERIVED_REFERENCE"] = gate.get("derived_reference")
    report["DERIVED_REFERENCE_APPROVED"] = "YES" if gate.get("derived_reference_approved") else "NO"

    if not args.generate:
        report["CURRENT_GATE"] = gate.get("stop") or "READY_TO_GENERATE_ISOLATION"
        report["exact_next_human_action"] = gate.get("ui_action")
        print(json.dumps(report, indent=2))
        return 0 if gate["ready"] else 2

    if not gate["ready"]:
        report["CURRENT_GATE"] = gate.get("stop")
        report["exact_remediation"] = gate.get("ui_action")
        print(json.dumps(report, indent=2))
        return 2

    pipe = CanonCreationPipeline(series_id)
    batch = pipe.generate_character_isolation_candidates(derived_id=args.derived_id)
    by_id = {c.candidate_id: c for c in batch.candidates}
    for slot, cid in (
        ("CANDIDATE A", "character-isolation-candidate-a"),
        ("CANDIDATE B", "character-isolation-candidate-b"),
        ("CANDIDATE C", "character-isolation-candidate-c"),
    ):
        c = by_id.get(cid)
        report[slot] = (
            {
                "path": c.file,
                "exists": bool(c.file and Path(c.file).is_file()),
                "seed": c.seed,
                "denoise": c.denoise,
                "cfg": c.cfg,
                "steps": c.steps,
                "sampler": c.sampler_name,
                "scheduler": c.scheduler,
                "workflow": c.workflow,
                "reference_ids": c.reference_ids,
            }
            if c
            else None
        )

    real = sum(
        1
        for c in batch.candidates
        if c.file and Path(c.file).is_file() and c.conditioning_method == "IMAGE_TO_IMAGE"
    )
    report["REAL_IMAGES"] = real
    report["batch_notes"] = batch.recommendation_notes
    report["batch_blocker"] = batch.blocker

    if real == 3 and batch.status == CanonStatus.AWAITING_HUMAN_CHARACTER_ISOLATION_REVIEW:
        report["CURRENT_GATE"] = "AWAITING_HUMAN_CHARACTER_ISOLATION_REVIEW"
        report["exact_next_human_action"] = (
            "Compare ORIGINAL / DERIVED / A / B / C in Streamlit → Character Isolation Compare. "
            "Do NOT approve style, generate Auntie Bev, scenes, episodes, or train LoRA."
        )
        print(json.dumps(report, indent=2))
        return 0

    report["CURRENT_GATE"] = (
        batch.status.value if hasattr(batch.status, "value") else str(batch.status)
    )
    print(json.dumps(report, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
