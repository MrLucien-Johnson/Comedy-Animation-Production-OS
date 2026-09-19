#!/usr/bin/env python3
"""Phase 2B: generate exactly three reference-grounded style recovery candidates."""

from __future__ import annotations

import argparse
import json

from capos.canon.pipeline import CanonCreationPipeline
from capos.canon.style_rejection import reject_phase2a_style_drift
from capos.core.status import CanonStatus
from capos.generation.capabilities import capability_matrix, select_production_provider
from capos.generation.provider_status import comfyui_dashboard_panel, provider_dashboard_status
from capos.hardware.profile import load_hardware_profile, resolve_generation_settings
from capos.production.storage import ensure_production_tree
from capos.references.ingestion import VisualReferenceStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 2B style recovery generation")
    parser.add_argument(
        "--set-id",
        default="likkle-jay-style-reference-set-v1",
        help="Approved style reference set id",
    )
    parser.add_argument(
        "--skip-reject",
        action="store_true",
        help="Skip re-applying Phase 2A drift rejection marker",
    )
    args = parser.parse_args()

    series_id = "likkle-jay"
    ensure_production_tree(series_id)
    if not args.skip_reject:
        reject_phase2a_style_drift(series_id)

    hw = load_hardware_profile()
    settings = resolve_generation_settings(hw)
    vstore = VisualReferenceStore(series_id)
    gate = vstore.style_recovery_gate()
    pipe = CanonCreationPipeline(series_id)

    report: dict = {
        "phase": "2B",
        "phase2a_candidates": "REJECTED",
        "rejection_reason": "NOT_CLOSE_ENOUGH_TO_ESTABLISHED_LIKKLE_JAY_STYLE",
        "gpu_profile": {
            "profile_id": hw.profile_id,
            "vram_class": hw.vram_class,
            "width": settings["width"],
            "height": settings["height"],
            "concurrency": settings["concurrency"],
        },
        "provider_matrix": capability_matrix(),
        "selected_production_provider": select_production_provider(),
        "comfyui": comfyui_dashboard_panel(),
        "providers": provider_dashboard_status(),
        "reference_ingestion": "READY" if gate["ready"] else "BLOCKED",
        "style_recovery_gate": gate,
        "reference_conditioning_method": "IMAGE_TO_IMAGE",
        "checkpoint": None,
        "style_recovery_candidates": {"count": 0, "batch": None},
        "character_production": "BLOCKED_UNTIL_STYLE_APPROVAL",
    }

    if not gate["ready"]:
        report["stop"] = "AWAITING_STYLE_REFERENCE_IMPORT"
        report["exact_next_human_action"] = (
            f"Import established Likkle Jay artwork into `{gate['import_folder']}` "
            f"via Streamlit → References → Import Visual Reference as STYLE_REFERENCE, "
            f"approve each, create/approve set `{gate['preferred_set_id']}` (3–8 images)."
        )
        print(json.dumps(report, indent=2))
        return 2

    ok, provider = pipe.can_generate_production()
    if not ok:
        batch = pipe.generate_style_recovery_candidates(count=3, set_id=args.set_id)
        report["style_recovery_candidates"] = {
            "count": len(batch.candidates),
            "batch": batch.model_dump(mode="json"),
        }
        report["stop"] = "BLOCKED_NO_PROVIDER"
        report["exact_next_human_action"] = (
            "Configure CAPOS_COMFYUI_URL + CAPOS_COMFYUI_CHECKPOINT on the RTX 3050 machine."
        )
        print(json.dumps(report, indent=2))
        return 3

    batch = pipe.generate_style_recovery_candidates(count=3, set_id=args.set_id)
    report["checkpoint"] = next((c.model for c in batch.candidates if c.model), None)
    report["style_reference_set"] = {
        "set_id": args.set_id,
        "count": len((vstore.get_set(args.set_id) or type("S", (), {"reference_ids": []})()).reference_ids),
    }
    report["style_recovery_candidates"] = {
        "count": len(batch.candidates),
        "status": batch.status.value if hasattr(batch.status, "value") else str(batch.status),
        "batch_id": batch.batch_id,
        "candidates": [
            {
                "candidate_id": c.candidate_id,
                "file": c.file,
                "seed": c.seed,
                "denoise": c.denoise,
                "conditioning_method": c.conditioning_method,
                "reference_ids": c.reference_ids,
                "reference_checksums": c.reference_checksums,
                "checkpoint": c.model,
                "workflow": c.workflow,
            }
            for c in batch.candidates
        ],
        "batch": batch.model_dump(mode="json"),
    }
    if batch.status == CanonStatus.AWAITING_HUMAN_STYLE_RECOVERY_REVIEW and batch.candidates:
        report["stop"] = "AWAITING_HUMAN_STYLE_RECOVERY_REVIEW"
        report["exact_next_human_action"] = (
            "Open Streamlit → Canon Candidates → style-recovery-batch-001 and "
            "Compare to Reference; review LINEWORK/SHAPE/COLOUR/SHADING/FACE/BACKGROUND/"
            "COMEDY/ANIME_DRIFT/PHOTOREALISM/OVER_DETAILING/OVERALL_CONTINUITY. "
            "Do NOT generate character masters until style recovery is approved."
        )
        report["engineering_readiness"] = "READY"
        report["style_readiness"] = "AWAITING_HUMAN_REVIEW"
        print(json.dumps(report, indent=2))
        return 0

    report["stop"] = batch.status.value if hasattr(batch.status, "value") else str(batch.status)
    report["exact_next_human_action"] = batch.blocker or "Inspect batch notes"
    report["engineering_readiness"] = "PARTIAL"
    report["style_readiness"] = "NOT_READY"
    print(json.dumps(report, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
