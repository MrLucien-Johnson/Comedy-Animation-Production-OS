"""Canon candidate batches + human selection workflow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from capos.core.errors import ValidationError
from capos.core.paths import series_dir
from capos.core.schemas import utcnow
from capos.core.status import CanonStatus, CanonStep


class CandidateAsset(BaseModel):
    candidate_id: str
    file: str | None = None
    checksum: str | None = None
    backend: str | None = None
    provider: str | None = None
    model: str | None = None
    model_family: str | None = None
    model_licence_status: str | None = None
    seed: int | None = None
    prompt_version: str | None = None
    positive_prompt: str | None = None
    negative_prompt: str | None = None
    workflow: str | None = None
    workflow_id: str | None = None
    workflow_version: str | None = None
    generation_resolution: str | None = None
    width: int | None = None
    height: int | None = None
    steps: int | None = None
    cfg: float | None = None
    sampler_name: str | None = None
    scheduler: str | None = None
    denoise: float | None = None
    duration_ms: int | None = None
    generated_at: str | None = None
    original_output_path: str | None = None
    smoke_test: bool = False
    qa_summary: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    status: CanonStatus = CanonStatus.CANDIDATE
    non_production: bool = False
    superseded_by: str | None = None
    regenerates: str | None = None  # prior candidate_id if same-seed regen


class CandidateBatch(BaseModel):
    batch_id: str
    series_id: str
    step: CanonStep
    target_asset_id: str  # e.g. style-likkle-jay-v1 once selected
    parent_asset_ids: list[str] = Field(default_factory=list)
    status: CanonStatus = CanonStatus.AWAITING_HUMAN_SELECTION
    candidates: list[CandidateAsset] = Field(default_factory=list)
    selected_candidate_id: str | None = None
    recommendation_notes: list[str] = Field(default_factory=list)
    blocker: str | None = None
    created_at: str = Field(default_factory=lambda: utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: utcnow().isoformat())


class CandidateStore:
    def __init__(self, series_id: str, *, root: Path | None = None) -> None:
        self.series_id = series_id
        self.root = root
        self.path = series_dir(series_id, root=root) / "canon" / "candidate_batches.json"

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"batches": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    def upsert(self, batch: CandidateBatch) -> CandidateBatch:
        batch.updated_at = utcnow().isoformat()
        data = self._load()
        data.setdefault("batches", {})[batch.batch_id] = batch.model_dump(mode="json")
        self._save(data)
        return batch

    def get(self, batch_id: str) -> CandidateBatch | None:
        raw = self._load().get("batches", {}).get(batch_id)
        return CandidateBatch.model_validate(raw) if raw else None

    def list_batches(self, *, step: CanonStep | None = None) -> list[CandidateBatch]:
        batches = [
            CandidateBatch.model_validate(v) for v in self._load().get("batches", {}).values()
        ]
        if step:
            batches = [b for b in batches if b.step == step]
        return sorted(batches, key=lambda b: b.created_at)

    def awaiting_human(self) -> list[CandidateBatch]:
        return [
            b
            for b in self.list_batches()
            if b.status == CanonStatus.AWAITING_HUMAN_SELECTION and b.candidates
        ]

    def select_candidate(self, batch_id: str, candidate_id: str) -> CandidateBatch:
        batch = self.get(batch_id)
        if not batch:
            raise ValidationError(f"Unknown batch {batch_id}")
        ids = {c.candidate_id for c in batch.candidates}
        if candidate_id not in ids:
            raise ValidationError(f"Candidate {candidate_id} not in batch {batch_id}")
        chosen = next(c for c in batch.candidates if c.candidate_id == candidate_id)
        if not chosen.file or not Path(chosen.file).is_file():
            raise ValidationError("Cannot select candidate without an image file")
        if chosen.non_production:
            raise ValidationError(
                "Cannot select non-production (mock) art as visual canon",
                hint="Generate with a real provider or import a real image.",
            )
        batch.selected_candidate_id = candidate_id
        batch.status = CanonStatus.REVIEW_REQUIRED
        for c in batch.candidates:
            c.status = (
                CanonStatus.CANDIDATE if c.candidate_id == candidate_id else CanonStatus.REJECTED
            )
        return self.upsert(batch)
