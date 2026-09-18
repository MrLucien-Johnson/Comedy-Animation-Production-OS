#!/usr/bin/env python3
"""Phase 2: attempt style-master candidate generation (real provider only)."""

from __future__ import annotations

import json

from capos.canon.pipeline import CanonCreationPipeline
from capos.generation.capabilities import capability_matrix, select_production_provider
from capos.production.storage import ensure_production_tree


def main() -> int:
    ensure_production_tree("likkle-jay")
    pipe = CanonCreationPipeline("likkle-jay")
    report = {
        "provider_matrix": capability_matrix(),
        "selected_production_provider": select_production_provider(),
        "next": pipe.next_actionable_step(),
    }
    ok, provider = pipe.can_generate_production()
    if not ok:
        report["style_batch"] = pipe.generate_style_candidates().model_dump(mode="json")
        report["engineering_note"] = (
            "No production provider — batch marked BLOCKED_NO_PROVIDER. "
            "Mock art was NOT used as production candidates."
        )
        print(json.dumps(report, indent=2))
        return 2

    batch = pipe.generate_style_candidates(count=3)
    report["style_batch"] = batch.model_dump(mode="json")
    report["human_action"] = (
        "AWAITING_HUMAN_SELECTION — open Streamlit Canon Candidates and choose style master."
    )
    print(json.dumps(report, indent=2))
    return 0 if batch.candidates else 1


if __name__ == "__main__":
    raise SystemExit(main())
