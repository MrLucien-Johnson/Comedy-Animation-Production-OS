#!/usr/bin/env python3
"""Phase 2B: mark Phase 2A style candidates HUMAN_REJECTED_STYLE_DRIFT."""

from __future__ import annotations

import json
import sys

from capos.canon.pipeline import CanonCreationPipeline
from capos.canon.style_rejection import reject_phase2a_style_drift
from capos.production.storage import ensure_production_tree
from capos.references.ingestion import VisualReferenceStore


def main() -> int:
    series_id = "likkle-jay"
    ensure_production_tree(series_id)
    rejection = reject_phase2a_style_drift(series_id)
    gate = VisualReferenceStore(series_id).style_recovery_gate()
    next_step = CanonCreationPipeline(series_id).next_actionable_step()
    report = {
        "phase": "2B",
        "phase2a_candidates": "REJECTED",
        "rejection": rejection,
        "rejection_reason": "NOT_CLOSE_ENOUGH_TO_ESTABLISHED_LIKKLE_JAY_STYLE",
        "reference_ingestion": "READY" if gate["ready"] else "BLOCKED",
        "style_recovery_gate": gate,
        "next_actionable_step": next_step,
        "stop": gate.get("stop") or next_step.get("stop") or "AWAITING_STYLE_REFERENCE_IMPORT",
        "character_production": "BLOCKED_UNTIL_STYLE_APPROVAL",
        "exact_next_human_action": (
            gate.get("ui_action")
            if not gate["ready"]
            else "Run scripts/phase2b_style_recovery_generate.py after approving references"
        ),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
