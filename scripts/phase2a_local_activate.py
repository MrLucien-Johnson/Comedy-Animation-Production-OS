#!/usr/bin/env python3
"""Phase 2A local activation — connect ComfyUI, validate workflow, optional smoke + 3 style candidates.

Run on the PRODUCTION MACHINE (RTX 3050) where ComfyUI Desktop is listening.
Cloud/agent environments without access to that GPU will report LOCAL_EXECUTION_REQUIRED.
Never falls back to mock.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from capos.generation.comfyui.workflows import describe_workflow, workflow_is_configured
from capos.generation.comfyui_backend import ComfyUIBackend
from capos.generation.model_licence import (
    environment_runtime_status,
    load_model_provenance,
    production_licence_gate,
)
from capos.generation.provider_status import comfyui_dashboard_panel
from capos.generation.smoke import run_provider_smoke_test, run_style_master_three
from capos.hardware.profile import load_hardware_profile, resolve_generation_settings
from capos.pipeline.readiness import evaluate_season_production_ready
from capos.production.storage import ensure_production_tree


def _activate(run_smoke: bool, generate_style: bool) -> dict:
    ensure_production_tree("likkle-jay")
    runtime = environment_runtime_status()
    panel = comfyui_dashboard_panel()
    prov = load_model_provenance()
    hw = load_hardware_profile()
    gen = resolve_generation_settings(hw)
    report: dict = {
        "phase": "2A-local-activate",
        "runtime": runtime,
        "hardware": hw.model_dump(mode="json"),
        "generation_settings": gen,
        "comfyui_panel": panel,
        "model_provenance": prov,
        "licence_gate": dict(zip(("ok", "reason"), production_licence_gate(), strict=True)),
    }

    if runtime["local_provider_status"] == "LOCAL_EXECUTION_REQUIRED":
        report["outcome"] = "LOCAL_EXECUTION_REQUIRED"
        report["stop"] = "LOCAL_EXECUTION_REQUIRED"
        report["manual_actions"] = [
            "On the RTX 3050 production machine: start ComfyUI Desktop API (typically :8188)",
            "Copy .env.example → .env and set:",
            "  CAPOS_COMFYUI_URL=http://127.0.0.1:8188",
            "  CAPOS_COMFYUI_CHECKPOINT=toonyou_beta6.safetensors",
            "  CAPOS_COMFYUI_WORKFLOW=style-master-toonyou-beta6.json",
            "  # or CAPOS_COMFYUI_WORKFLOW_PATH=/path/to/exported_api_workflow.json",
            "  CAPOS_COMFYUI_MODEL_LICENCE=<note from source review>",
            "Optionally: ComfyUI → Save (API Format) → workflows/comfyui/style-master-low-vram.json",
            "Re-run: python scripts/phase2a_local_activate.py --smoke --style",
        ]
        return report

    backend = ComfyUIBackend()
    ok, reason = backend.available()
    report["connection"] = {"ok": ok, "reason": reason}
    if not ok:
        report["outcome"] = "LOCAL_EXECUTION_REQUIRED"
        report["stop"] = "ComfyUI unreachable"
        return report

    ckpt = os.environ.get("CAPOS_COMFYUI_CHECKPOINT", "toonyou_beta6.safetensors")
    present, present_reason = backend.client().checkpoint_present(ckpt)
    report["checkpoint"] = {
        "name": ckpt,
        "listed": present,
        "reason": present_reason,
        "note": "If API cannot list models, confirm file exists under ComfyUI models/checkpoints/",
    }

    wf_ok, wf_reason = workflow_is_configured()
    report["workflow"] = {"configured": wf_ok, "reason": wf_reason}
    try:
        report["workflow"]["describe"] = describe_workflow()
    except Exception as exc:  # noqa: BLE001
        report["workflow"]["describe_error"] = str(exc)

    if not wf_ok:
        report["outcome"] = "SETUP_REQUIRED"
        report["stop"] = wf_reason
        return report

    report["capabilities"] = backend.health_check().get("capabilities")
    report["local_provider_status"] = "LOCAL_RUNTIME_VERIFIED"

    if run_smoke:
        report["smoke_test"] = run_provider_smoke_test()
        if not report["smoke_test"].get("ok"):
            report["outcome"] = "SMOKE_FAILED"
            report["stop"] = report["smoke_test"].get("reason")
            return report

    if generate_style:
        style = run_style_master_three()
        report["style_candidates"] = style
        report["actual_image_count"] = style.get("candidate_count", 0)
        if style.get("candidate_count") == 3:
            report["outcome"] = "AWAITING_HUMAN_STYLE_SELECTION"
            report["stop"] = "AWAITING_HUMAN_STYLE_SELECTION"
            report["human_action"] = (
                "Open Streamlit → Canon Candidates → SELECT one style → "
                "APPROVE/LOCK only after licence review. Do not generate characters yet."
            )
        else:
            report["outcome"] = "STYLE_GENERATION_INCOMPLETE"
            report["stop"] = style.get("status")
        report["readiness"] = evaluate_season_production_ready("likkle-jay").model_dump(
            mode="json"
        )
        return report

    report["outcome"] = "LOCAL_RUNTIME_VERIFIED"
    report["stop"] = "Provider verified — pass --smoke and/or --style to generate"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="CAPOS Phase 2A local ComfyUI activation")
    parser.add_argument(
        "--smoke", action="store_true", help="Run PROVIDER_SMOKE_TEST (non-canon)"
    )
    parser.add_argument(
        "--style",
        action="store_true",
        help="Generate exactly three style-master candidates sequentially",
    )
    args = parser.parse_args()
    report = _activate(run_smoke=args.smoke, generate_style=args.style)
    print(json.dumps(report, indent=2, default=str))
    outcome = report.get("outcome")
    if outcome in {"AWAITING_HUMAN_STYLE_SELECTION", "LOCAL_RUNTIME_VERIFIED"}:
        return 0
    if outcome == "LOCAL_EXECUTION_REQUIRED":
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
