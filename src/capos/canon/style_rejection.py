"""Reject Phase 2A text-only style candidates for established-style drift."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from capos.canon.candidates import CandidateAsset, CandidateBatch, CandidateStore
from capos.core.schemas import utcnow
from capos.core.status import CanonStatus, CanonStep


REJECTION_CODE = "NOT_CLOSE_ENOUGH_TO_ESTABLISHED_LIKKLE_JAY_STYLE"
REJECTION_STATUS = CanonStatus.HUMAN_REJECTED_STYLE_DRIFT
PHASE2A_BATCH_ID = "style-master-batch-001"
PHASE2A_CANDIDATE_IDS = (
    "style-master-candidate-001",
    "style-master-candidate-002",
    "style-master-candidate-003",
)


def reject_phase2a_style_drift(
    series_id: str = "likkle-jay",
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    """Preserve Phase 2A candidates + provenance; mark HUMAN_REJECTED_STYLE_DRIFT.

    Never deletes files. Never promotes to canon.
    """
    store = CandidateStore(series_id, root=root)
    batch = store.get(PHASE2A_BATCH_ID)
    notes = [
        "Phase 2B: text-only style invention rejected — STYLE RECOVERY via references required.",
        f"rejection_code={REJECTION_CODE}",
    ]
    if not batch:
        batch = CandidateBatch(
            batch_id=PHASE2A_BATCH_ID,
            series_id=series_id,
            step=CanonStep.STYLE_MASTER,
            target_asset_id="style-likkle-jay-v1",
            status=REJECTION_STATUS,
            candidates=[],
            recommendation_notes=notes,
            blocker="No Phase 2A candidates on this machine — rejection recorded as policy marker",
        )
        store.upsert(batch)
        return {
            "ok": True,
            "batch_id": PHASE2A_BATCH_ID,
            "rejected_count": 0,
            "status": REJECTION_STATUS.value,
            "note": "Batch created as rejection marker; no candidate files present in this environment",
        }

    rejected = 0
    for cand in batch.candidates:
        if cand.candidate_id in PHASE2A_CANDIDATE_IDS or cand.candidate_id.startswith(
            "style-master-candidate-"
        ):
            cand.status = REJECTION_STATUS
            cand.rejection_code = REJECTION_CODE
            cand.rejection_reason = (
                "Technically valid but visual drift from established Likkle Jay style: "
                "anime/adventure lean, elongated proportions, angular faces, cinematic detail."
            )
            cand.batch_kind = "phase2a_style"
            cand.qa_summary = {
                **cand.qa_summary,
                "HUMAN_REVIEW": REJECTION_STATUS.value,
                "rejection_code": REJECTION_CODE,
                "do_not_select_as_canon": True,
            }
            rejected += 1

    # Ensure the three IDs are recorded even if only files exist without batch entries
    known = {c.candidate_id for c in batch.candidates}
    for cid in PHASE2A_CANDIDATE_IDS:
        if cid not in known:
            batch.candidates.append(
                CandidateAsset(
                    candidate_id=cid,
                    status=REJECTION_STATUS,
                    rejection_code=REJECTION_CODE,
                    rejection_reason="Rejected by Phase 2B policy (slot reserved)",
                    batch_kind="phase2a_style",
                    qa_summary={"do_not_select_as_canon": True},
                    non_production=False,
                )
            )
            rejected += 1

    batch.status = REJECTION_STATUS
    batch.selected_candidate_id = None
    batch.recommendation_notes = notes + list(batch.recommendation_notes or [])
    batch.blocker = (
        "All Phase 2A text-only style candidates HUMAN_REJECTED_STYLE_DRIFT — "
        "import established Likkle Jay artwork and run style recovery"
    )
    batch.updated_at = utcnow().isoformat()
    store.upsert(batch)
    return {
        "ok": True,
        "batch_id": PHASE2A_BATCH_ID,
        "rejected_count": rejected,
        "status": REJECTION_STATUS.value,
        "rejection_code": REJECTION_CODE,
        "candidates": [c.candidate_id for c in batch.candidates],
    }
