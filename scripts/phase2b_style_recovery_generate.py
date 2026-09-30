#!/usr/bin/env python3
"""Phase 2B: generate exactly THREE genuine ComfyUI img2img style-recovery candidates.

Requires:
  CAPOS_COMFYUI_URL=http://127.0.0.1:8188
  CAPOS_COMFYUI_CHECKPOINT=toonyou_beta6.safetensors
  Approved likkle-jay-style-reference-set-v1

Refuses mock and txt2img fallbacks. Stops at AWAITING_HUMAN_STYLE_RECOVERY_REVIEW.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from capos.canon.pipeline import CanonCreationPipeline
from capos.canon.prompts import STYLE_RECOVERY_DEFAULT_DENOISE
from capos.canon.style_rejection import reject_phase2a_style_drift
from capos.core.status import CanonStatus
from capos.generation.comfyui.style_recovery_health import (
    STYLE_RECOVERY_WORKFLOW,
    assert_img2img_workflow,
    comfyui_style_recovery_healthcheck,
    select_target_reference,
)
from capos.generation.comfyui.workflows import describe_workflow
from capos.hardware.profile import load_hardware_profile, resolve_generation_settings
from capos.production.storage import ensure_production_tree
from capos.references.ingestion import VisualReferenceStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 2B genuine img2img style recovery")
    parser.add_argument("--set-id", default="likkle-jay-style-reference-set-v1")
    parser.add_argument(
        "--target",
        default="likkle-jay",
        choices=["likkle-jay", "auntie-bev", "kitchen", "cookie-jar"],
        help="Which approved reference family to condition on (do not blend)",
    )
    parser.add_argument(
        "--denoise",
        type=float,
        default=STYLE_RECOVERY_DEFAULT_DENOISE,
        help="Shared img2img denoise for all 3 candidates (0.30–0.45); seeds vary",
    )
    parser.add_argument("--skip-reject", action="store_true")
    parser.add_argument(
        "--health-only",
        action="store_true",
        help="Run ComfyUI/img2img health check and exit without generating",
    )
    args = parser.parse_args()

    series_id = "likkle-jay"
    ensure_production_tree(series_id)
    if not args.skip_reject:
        reject_phase2a_style_drift(series_id)

    # Prefer operator env; document defaults
    os.environ.setdefault("CAPOS_COMFYUI_URL", "http://127.0.0.1:8188")
    os.environ.setdefault("CAPOS_COMFYUI_CHECKPOINT", "toonyou_beta6.safetensors")

    hw = load_hardware_profile()
    settings = resolve_generation_settings(hw)
    vstore = VisualReferenceStore(series_id)
    gate = vstore.style_recovery_gate()
    pipe = CanonCreationPipeline(series_id)

    # Clarify: style-master is txt2img — must NOT be used
    master_desc = {}
    try:
        master_desc = describe_workflow("style-master-toonyou-beta6.json")
    except Exception as exc:  # noqa: BLE001
        master_desc = {"error": str(exc)}
    recovery_img2img = assert_img2img_workflow(STYLE_RECOVERY_WORKFLOW)

    primary_ref = None
    if gate["ready"]:
        ref_set = vstore.get_set(args.set_id)
        refs = []
        if ref_set:
            for rid in ref_set.reference_ids:
                r = vstore.get(rid)
                if r and Path(r.file).is_file() and r.status == CanonStatus.APPROVED:
                    refs.append(r)
        if refs:
            primary_ref = select_target_reference(refs, target=args.target)

    health = comfyui_style_recovery_healthcheck(
        reference_path=primary_ref.file if primary_ref else None,
    )

    report: dict = {
        "phase": "2B",
        "COMFYUI_CONNECTION": health.get("comfyui_connection"),
        "GPU": "NVIDIA GeForce RTX 3050",
        "VRAM": "6144 MB",
        "gpu_profile": {
            "profile_id": hw.profile_id,
            "vram_class": hw.vram_class,
            "width": settings["width"],
            "height": settings["height"],
            "concurrency": settings["concurrency"],
        },
        "CHECKPOINT": health.get("checkpoint") or os.environ.get("CAPOS_COMFYUI_CHECKPOINT"),
        "WORKFLOW": STYLE_RECOVERY_WORKFLOW,
        "WORKFLOW_MODE": health.get("workflow_mode") or recovery_img2img.get("mode"),
        "WORKFLOW_ID": recovery_img2img.get("workflow_id"),
        "REFERENCE": (
            {
                "reference_id": primary_ref.reference_id,
                "file": primary_ref.file,
                "checksum": primary_ref.checksum,
                "target": args.target,
            }
            if primary_ref
            else None
        ),
        "DENOISE": args.denoise,
        "TXT2IMG_FALLBACK": "DISABLED",
        "MOCK_CANDIDATES": 0,
        "style_master_workflow_note": {
            "file": "style-master-toonyou-beta6.json",
            "mode": (master_desc.get("validation") or {}).get("mode"),
            "LoadImage": bool(
                ((master_desc.get("validation") or {}).get("roles") or {}).get("load_image")
            ),
            "VAEEncode": bool(
                ((master_desc.get("validation") or {}).get("roles") or {}).get("vae_encode")
            ),
            "IMAGE_TO_IMAGE": False,
            "phase2b_uses_this": False,
            "note": "Phase 2A txt2img — NOT used for style recovery",
        },
        "style_recovery_workflow": recovery_img2img,
        "health": health,
        "style_recovery_gate": gate,
        "REAL_CANDIDATES_GENERATED": "0/3",
        "CURRENT_GATE": None,
        "character_production": "BLOCKED_UNTIL_STYLE_APPROVAL",
    }

    if not gate["ready"]:
        report["CURRENT_GATE"] = "AWAITING_STYLE_REFERENCE_IMPORT"
        report["exact_next_human_action"] = gate.get("ui_action")
        print(json.dumps(report, indent=2))
        return 2

    if not health.get("ok"):
        report["CURRENT_GATE"] = "BLOCKED_COMFYUI_IMG2IMG_HEALTHCHECK"
        report["exact_remediation"] = health.get("remediation")
        print(json.dumps(report, indent=2))
        return 3

    if args.health_only:
        report["CURRENT_GATE"] = "HEALTH_OK_READY_TO_GENERATE"
        print(json.dumps(report, indent=2))
        return 0

    batch = pipe.generate_style_recovery_candidates(
        count=3,
        set_id=args.set_id,
        target=args.target,
        denoise=args.denoise,
    )
    real_files = []
    for c in batch.candidates:
        if (
            c.file
            and Path(c.file).is_file()
            and c.conditioning_method == "IMAGE_TO_IMAGE"
            and c.backend == "comfyui"
            and not c.non_production
        ):
            real_files.append(c)

    n = len(real_files)
    report["REAL_CANDIDATES_GENERATED"] = f"{n}/3"
    report["MOCK_CANDIDATES"] = sum(1 for c in batch.candidates if c.non_production or c.backend == "mock")
    report["candidates"] = [
        {
            "candidate_id": c.candidate_id,
            "file": c.file,
            "exists": bool(c.file and Path(c.file).is_file()),
            "seed": c.seed,
            "denoise": c.denoise,
            "cfg": c.cfg,
            "steps": c.steps,
            "sampler": c.sampler_name,
            "scheduler": c.scheduler,
            "checkpoint": c.model,
            "workflow": c.workflow,
            "workflow_id": c.workflow_id,
            "conditioning_method": c.conditioning_method,
            "reference_ids": c.reference_ids,
            "reference_checksums": c.reference_checksums,
        }
        for c in batch.candidates
    ]
    report["CANDIDATE_PATHS"] = {
        "Candidate 1": next(
            (c.file for c in real_files if c.candidate_id.endswith("001")), None
        ),
        "Candidate 2": next(
            (c.file for c in real_files if c.candidate_id.endswith("002")), None
        ),
        "Candidate 3": next(
            (c.file for c in real_files if c.candidate_id.endswith("003")), None
        ),
    }
    report["batch_notes"] = batch.recommendation_notes
    report["batch_blocker"] = batch.blocker

    if n == 3 and batch.status == CanonStatus.AWAITING_HUMAN_STYLE_RECOVERY_REVIEW:
        report["CURRENT_GATE"] = "AWAITING_HUMAN_STYLE_RECOVERY_REVIEW"
        report["exact_next_human_action"] = (
            "Visually compare Candidate 1/2/3 against the established Likkle Jay reference. "
            "Do NOT approve yet. Do NOT generate Auntie Bev / scenes / episodes. "
            "Do NOT update canonical visual assets."
        )
        print(json.dumps(report, indent=2))
        return 0

    report["CURRENT_GATE"] = (
        batch.status.value if hasattr(batch.status, "value") else str(batch.status)
    )
    report["exact_remediation"] = batch.blocker or "Inspect batch_notes — real PNG count < 3"
    print(json.dumps(report, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
