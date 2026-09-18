#!/usr/bin/env python3
"""Phase 2A: ComfyUI connection → smoke → exactly three style candidates (sequential)."""

from __future__ import annotations

import json
import sys

from capos.generation.provider_status import comfyui_dashboard_panel
from capos.generation.smoke import run_provider_smoke_test, run_style_master_three
from capos.hardware.profile import detect_gpu, load_hardware_profile, resolve_generation_settings
from capos.pipeline.readiness import evaluate_season_production_ready
from capos.production.storage import ensure_production_tree


def main() -> int:
    ensure_production_tree("likkle-jay")
    gpu = detect_gpu()
    hw = load_hardware_profile()
    gen = resolve_generation_settings(hw)
    panel = comfyui_dashboard_panel()
    report: dict = {
        "phase": "2A",
        "gpu": gpu,
        "hardware_profile": hw.model_dump(mode="json"),
        "generation_settings": gen,
        "comfyui": panel,
        "local_provider": panel.get("local_provider", "SETUP_REQUIRED"),
    }

    if panel.get("local_provider") != "AVAILABLE" or not panel.get("connection_ok"):
        report["outcome"] = "A"
        report["stop"] = "LOCAL_PROVIDER = SETUP_REQUIRED"
        report["manual_actions"] = [
            "Install ComfyUI on the RTX 3050 production machine (see docs/COMFYUI_LOCAL_SETUP.md)",
            "Start ComfyUI API server (confirm with `python main.py --help` for low-VRAM flags)",
            "Set CAPOS_COMFYUI_URL=http://127.0.0.1:8188",
            "Place one SD1.5-class cartoon checkpoint; set CAPOS_COMFYUI_CHECKPOINT",
            "Record licence in CAPOS_COMFYUI_MODEL_LICENCE (see docs/MODEL_SELECTION.md)",
            "Export/clear template_only on style-master-low-vram.json or set CAPOS_COMFYUI_WORKFLOW_PATH",
            "Re-run: python scripts/phase2a_comfyui_smoke_and_style.py",
        ]
        report["smoke_test"] = None
        report["style_candidates"] = None
        report["actual_production_images_created"] = 0
        print(json.dumps(report, indent=2))
        return 2

    smoke = run_provider_smoke_test()
    report["smoke_test"] = smoke
    if not smoke.get("ok"):
        report["outcome"] = "A"
        report["stop"] = "LOCAL_PROVIDER = SETUP_REQUIRED (smoke failed)"
        report["manual_actions"] = [
            str(smoke.get("reason")),
            "Fix model/workflow per docs/COMFYUI_LOCAL_SETUP.md then re-run this script",
        ]
        print(json.dumps(report, indent=2))
        return 2

    style = run_style_master_three()
    report["style_candidates"] = style
    report["actual_production_images_created"] = style.get("candidate_count", 0)
    report["readiness"] = evaluate_season_production_ready("likkle-jay").model_dump(mode="json")

    if style.get("candidate_count") == 3:
        report["outcome"] = "B"
        report["stop"] = "AWAITING_HUMAN_STYLE_SELECTION"
        report["human_action"] = (
            "Open Streamlit → Canon Candidates → select ONE style master → "
            "APPROVE/LOCK on Canon page. Do not proceed to characters until style is locked."
        )
        print(json.dumps(report, indent=2))
        return 0

    report["outcome"] = "A"
    report["stop"] = "LOCAL_PROVIDER = SETUP_REQUIRED (style generation incomplete)"
    print(json.dumps(report, indent=2))
    return 1


if __name__ == "__main__":
    sys.exit(main())
