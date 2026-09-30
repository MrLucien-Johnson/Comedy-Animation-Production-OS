"""Mark Phase 2B style-recovery batch as technical success — not yet approved."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from capos.canon.candidates import CandidateStore
from capos.core.schemas import utcnow
from capos.core.status import CanonStatus


RECOVERY_BATCH_ID = "style-recovery-batch-001"
TECHNICAL_STATUS = CanonStatus.TECHNICAL_SUCCESS_STYLE_RECOVERY_NOT_YET_APPROVED


def mark_style_recovery_technical_success(
    series_id: str = "likkle-jay",
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    """Preserve recovery candidates + provenance; do NOT promote to canon.

    Human found sheet-layout contamination — character isolation (2B.1) required next.
    """
    store = CandidateStore(series_id, root=root)
    batch = store.get(RECOVERY_BATCH_ID)
    if not batch:
        return {
            "ok": False,
            "error": f"Batch {RECOVERY_BATCH_ID} not found",
            "status": None,
        }
    notes = [
        "TECHNICAL_SUCCESS_STYLE_RECOVERY_NOT_YET_APPROVED",
        "Real ComfyUI IMG2IMG candidates proved reference influence works.",
        "Human review: candidates reproduce character-sheet layout/text/annotations.",
        "Do NOT approve as series style canon. Do NOT promote to style-likkle-jay-v1.",
        "Next: Phase 2B.1 CHARACTER ISOLATION — crop front-facing Jay, generate clean standalone images.",
    ]
    for cand in batch.candidates:
        cand.qa_summary = {
            **cand.qa_summary,
            "HUMAN_REVIEW": TECHNICAL_STATUS.value,
            "do_not_select_as_canon": True,
            "sheet_layout_contamination": True,
            "phase": "2B",
        }
        # Keep CANDIDATE visual files; block selection via qa flag + batch status
    batch.status = TECHNICAL_STATUS
    batch.selected_candidate_id = None
    batch.recommendation_notes = notes + list(batch.recommendation_notes or [])
    batch.blocker = (
        "Style recovery technically successful but NOT approved — "
        "character-sheet composition contamination. Proceed to 2B.1 character isolation."
    )
    batch.updated_at = utcnow().isoformat()
    store.upsert(batch)
    return {
        "ok": True,
        "batch_id": RECOVERY_BATCH_ID,
        "status": TECHNICAL_STATUS.value,
        "candidate_count": len(batch.candidates),
        "candidates": [c.candidate_id for c in batch.candidates],
        "do_not_approve": True,
        "next": "AWAITING_DERIVED_REFERENCE / Phase 2B.1 CHARACTER ISOLATION",
    }
