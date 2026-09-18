"""Canon creation pipeline — dependency-ordered candidate generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from capos.canon.candidates import CandidateAsset, CandidateBatch, CandidateStore
from capos.canon.prompts import (
    AUNTIE_BEV_MASTER_PROMPT,
    BEDROOM_EMPTY_PROMPT,
    COOKIE_JAR_PROMPT,
    KITCHEN_EMPTY_PROMPT,
    LIKKLE_JAY_MASTER_PROMPT,
    LIVING_ROOM_EMPTY_PROMPT,
    STYLE_MASTER_PROMPT,
    STYLE_NEGATIVE,
    YARD_EMPTY_PROMPT,
)
from capos.core.errors import ValidationError
from capos.core.paths import project_root
from capos.core.schemas import CanonicalAssetRef
from capos.core.status import CanonStatus, CanonStep
from capos.generation.capabilities import capability_matrix, select_production_provider
from capos.generation.registry import _REGISTRY, record_provider_refusal
from capos.production.storage import ensure_production_tree, register_production_file
from capos.references.versioning import ReferenceStore

CANON_DEPENDENCIES: dict[CanonStep, list[str]] = {
    CanonStep.STYLE_MASTER: [],
    CanonStep.LIKKLE_JAY_MASTER: ["style-likkle-jay-v1"],
    CanonStep.AUNTIE_BEV_MASTER: ["style-likkle-jay-v1"],
    CanonStep.CHARACTER_TURNAROUNDS: ["character-likkle-jay-v1", "character-auntie-bev-v1"],
    CanonStep.CHARACTER_EXPRESSIONS: ["character-likkle-jay-v1", "character-auntie-bev-v1"],
    CanonStep.LOCATION_MASTERS: ["style-likkle-jay-v1"],
    CanonStep.PROP_MASTERS: ["style-likkle-jay-v1", "location-kitchen-v1"],
    CanonStep.GOLDEN_FRAMES: [
        "character-likkle-jay-v1",
        "location-kitchen-v1",
        "prop-cookie-jar-v1",
    ],
}


def _approved_with_file(store: ReferenceStore, asset_id: str) -> bool:
    ref = store.get(asset_id)
    if not ref:
        return False
    status = ref.status.value if hasattr(ref.status, "value") else str(ref.status)
    return (
        status in {"APPROVED", "LOCKED"}
        and bool(ref.effective_path)
        and Path(ref.effective_path).is_file()
    )


def missing_parents(store: ReferenceStore, step: CanonStep) -> list[str]:
    return [pid for pid in CANON_DEPENDENCIES.get(step, []) if not _approved_with_file(store, pid)]


class CanonCreationPipeline:
    """Generate SMALL candidate sets in dependency order. Never auto-approve."""

    def __init__(self, series_id: str = "likkle-jay", *, root: Path | None = None) -> None:
        self.series_id = series_id
        self.root = root
        self.store = ReferenceStore(series_id, root=root)
        self.batches = CandidateStore(series_id, root=root)
        ensure_production_tree(series_id, root=root)

    def provider_report(self) -> dict[str, Any]:
        return {
            "matrix": capability_matrix(),
            "selected": select_production_provider(),
        }

    def can_generate_production(self) -> tuple[bool, str]:
        sel = select_production_provider()
        if not sel.get("production_eligible") or not sel.get("name"):
            return False, sel.get("blocker") or sel.get("reason") or "No production provider"
        return True, sel["name"]

    def _generate_candidates(
        self,
        *,
        batch_id: str,
        step: CanonStep,
        target_asset_id: str,
        prompt: str,
        negative: str = STYLE_NEGATIVE,
        count: int = 3,
        parent_asset_ids: list[str] | None = None,
        category: str = "style",
        slug: str = "master",
        reference_images: list[str] | None = None,
        allow_mock_for_engineering_demo: bool = False,
    ) -> CandidateBatch:
        parents = parent_asset_ids or CANON_DEPENDENCIES.get(step, [])
        missing = [p for p in parents if not _approved_with_file(self.store, p)]
        if missing:
            batch = CandidateBatch(
                batch_id=batch_id,
                series_id=self.series_id,
                step=step,
                target_asset_id=target_asset_id,
                parent_asset_ids=parents,
                status=CanonStatus.DRAFT,
                blocker=f"Missing approved parent canon with image files: {', '.join(missing)}",
                recommendation_notes=["Resolve parent approvals before this step."],
            )
            return self.batches.upsert(batch)

        ok, provider_or_reason = self.can_generate_production()
        if not ok:
            if allow_mock_for_engineering_demo:
                # Explicit opt-in only — candidates marked non_production and cannot be selected as canon
                provider_name = "mock"
                non_prod = True
            else:
                batch = CandidateBatch(
                    batch_id=batch_id,
                    series_id=self.series_id,
                    step=step,
                    target_asset_id=target_asset_id,
                    parent_asset_ids=parents,
                    status=CanonStatus.BLOCKED_NO_PROVIDER,
                    blocker=provider_or_reason,
                    recommendation_notes=[
                        "Configure HF_TOKEN, local Diffusers, or ComfyUI.",
                        "Mock art will not be accepted as production canon.",
                    ],
                )
                return self.batches.upsert(batch)
        else:
            provider_name = provider_or_reason
            non_prod = False

        from capos.generation.registry import try_register_optional_backends

        try_register_optional_backends()
        if provider_name not in _REGISTRY:
            batch = CandidateBatch(
                batch_id=batch_id,
                series_id=self.series_id,
                step=step,
                target_asset_id=target_asset_id,
                parent_asset_ids=parents,
                status=CanonStatus.BLOCKED_NO_PROVIDER,
                blocker=f"Provider '{provider_name}' not registered",
            )
            return self.batches.upsert(batch)

        backend = _REGISTRY[provider_name]()
        refs = reference_images or []
        for pid in parents:
            pref = self.store.get(pid)
            if pref and pref.effective_path:
                refs.append(pref.effective_path)

        candidates: list[CandidateAsset] = []
        notes: list[str] = []
        base_root = Path(self.root) if self.root else project_root()
        for i in range(1, count + 1):
            cid = f"{batch_id}-c{i:03d}"
            out = (
                base_root
                / "production"
                / self.series_id
                / "candidates"
                / category
                / slug
                / f"{cid}.png"
            )
            out.parent.mkdir(parents=True, exist_ok=True)
            result = backend.generate_image(
                prompt=prompt,
                negative_prompt=negative,
                width=1024,
                height=1024,
                seed=1000 + i,
                reference_images=refs or None,
                output_path=out,
                settings={"capos_canon_step": step.value, "non_production": non_prod},
            )
            if result.refusal:
                record_provider_refusal(
                    backend=provider_name, prompt=prompt, refusal=result.refusal
                )
                notes.append(f"{cid}: PROVIDER_REFUSED — {result.refusal}")
                continue
            if (
                not result.success
                or not result.output_path
                or not Path(result.output_path).is_file()
            ):
                notes.append(f"{cid}: generation failed — {result.error}")
                continue
            meta = register_production_file(
                series_id=self.series_id,
                category=category,
                asset_slug=slug,
                source_path=Path(result.output_path),
                root=self.root,
                kind="candidate",
            )
            qa = {
                "FILE_CHECK": "PASS",
                "DIMENSION_CHECK": "PASS"
                if Path(result.output_path).stat().st_size > 0
                else "FAIL",
                "VISUAL_IDENTITY": "REQUIRES_HUMAN_REVIEW",
                "non_production": non_prod,
            }
            candidates.append(
                CandidateAsset(
                    candidate_id=cid,
                    file=meta["file"],
                    checksum=meta["checksum"],
                    backend=provider_name,
                    model=result.model,
                    seed=result.seed,
                    qa_summary=qa,
                    status=CanonStatus.CANDIDATE,
                    non_production=non_prod,
                )
            )

        status = (
            CanonStatus.AWAITING_HUMAN_SELECTION
            if candidates and not non_prod
            else (
                CanonStatus.AWAITING_HUMAN_SELECTION
                if candidates and non_prod
                else CanonStatus.BLOCKED_NO_PROVIDER
            )
        )
        # Even mock candidates can be shown for UI engineering, but selection is blocked
        if candidates and non_prod:
            notes.append(
                "Candidates are MOCK/non-production — human selection as canon is blocked."
            )
            status = CanonStatus.AWAITING_HUMAN_SELECTION

        batch = CandidateBatch(
            batch_id=batch_id,
            series_id=self.series_id,
            step=step,
            target_asset_id=target_asset_id,
            parent_asset_ids=parents,
            status=status if candidates else CanonStatus.BLOCKED_NO_PROVIDER,
            candidates=candidates,
            recommendation_notes=notes or ["Review candidates in Canon UI; do not auto-approve."],
            blocker=None if candidates else "No successful generation outputs",
        )
        return self.batches.upsert(batch)

    def generate_style_candidates(self, *, count: int = 3) -> CandidateBatch:
        return self._generate_candidates(
            batch_id="style-master-batch-001",
            step=CanonStep.STYLE_MASTER,
            target_asset_id="style-likkle-jay-v1",
            prompt=STYLE_MASTER_PROMPT,
            count=count,
            category="style",
            slug="style-master",
        )

    def generate_likkle_jay_candidates(self, *, count: int = 3) -> CandidateBatch:
        return self._generate_candidates(
            batch_id="character-likkle-jay-batch-001",
            step=CanonStep.LIKKLE_JAY_MASTER,
            target_asset_id="character-likkle-jay-v1",
            prompt=LIKKLE_JAY_MASTER_PROMPT,
            count=count,
            category="characters",
            slug="likkle-jay",
        )

    def generate_auntie_bev_candidates(self, *, count: int = 3) -> CandidateBatch:
        return self._generate_candidates(
            batch_id="character-auntie-bev-batch-001",
            step=CanonStep.AUNTIE_BEV_MASTER,
            target_asset_id="character-auntie-bev-v1",
            prompt=AUNTIE_BEV_MASTER_PROMPT,
            count=count,
            category="characters",
            slug="auntie-bev",
        )

    def generate_location_candidates(self, location: str, *, count: int = 3) -> CandidateBatch:
        prompts = {
            "kitchen": KITCHEN_EMPTY_PROMPT,
            "living-room": LIVING_ROOM_EMPTY_PROMPT,
            "yard": YARD_EMPTY_PROMPT,
            "bedroom": BEDROOM_EMPTY_PROMPT,
        }
        targets = {
            "kitchen": "location-kitchen-v1",
            "living-room": "location-living-room-v1",
            "yard": "location-yard-v1",
            "bedroom": "location-jay-bedroom-v1",
        }
        if location not in prompts:
            raise ValidationError(f"Unknown location {location}")
        return self._generate_candidates(
            batch_id=f"location-{location}-batch-001",
            step=CanonStep.LOCATION_MASTERS,
            target_asset_id=targets[location],
            prompt=prompts[location],
            count=count,
            category="locations",
            slug=location,
        )

    def generate_cookie_jar_candidates(self, *, count: int = 3) -> CandidateBatch:
        return self._generate_candidates(
            batch_id="prop-cookie-jar-batch-001",
            step=CanonStep.PROP_MASTERS,
            target_asset_id="prop-cookie-jar-v1",
            prompt=COOKIE_JAR_PROMPT,
            count=count,
            category="props",
            slug="cookie-jar",
        )

    def promote_selection_to_canon(self, batch_id: str, candidate_id: str) -> CanonicalAssetRef:
        """Human-selected candidate → attach to target asset as CANDIDATE then require explicit approve."""
        batch = self.batches.select_candidate(batch_id, candidate_id)
        chosen = next(c for c in batch.candidates if c.candidate_id == candidate_id)
        # Copy into canon candidates path registration
        meta = register_production_file(
            series_id=self.series_id,
            category="canon-pending",
            asset_slug=batch.target_asset_id,
            source_path=Path(chosen.file),
            root=self.root,
            kind="candidate",
        )
        ref = self.store.get(batch.target_asset_id)
        if not ref:
            raise ValidationError(f"Target asset missing: {batch.target_asset_id}")
        attached = self.store.attach_file(
            batch.target_asset_id, meta["file"], source="generated_candidate"
        )
        batch.status = CanonStatus.REVIEW_REQUIRED
        self.batches.upsert(batch)
        return attached

    def next_actionable_step(self) -> dict[str, Any]:
        """Report which step can proceed and what is awaiting human selection."""
        awaiting = self.batches.awaiting_human()
        for step in (
            CanonStep.STYLE_MASTER,
            CanonStep.LIKKLE_JAY_MASTER,
            CanonStep.AUNTIE_BEV_MASTER,
            CanonStep.CHARACTER_TURNAROUNDS,
            CanonStep.CHARACTER_EXPRESSIONS,
            CanonStep.LOCATION_MASTERS,
            CanonStep.PROP_MASTERS,
            CanonStep.GOLDEN_FRAMES,
        ):
            missing = missing_parents(self.store, step)
            ok, provider = self.can_generate_production()
            if missing:
                continue
            # If target already approved, skip
            # Find primary target for step
            targets = {
                CanonStep.STYLE_MASTER: ["style-likkle-jay-v1"],
                CanonStep.LIKKLE_JAY_MASTER: ["character-likkle-jay-v1"],
                CanonStep.AUNTIE_BEV_MASTER: ["character-auntie-bev-v1"],
            }
            if step in targets and all(_approved_with_file(self.store, t) for t in targets[step]):
                continue
            return {
                "step": step.value,
                "missing_parents": missing,
                "provider_ok": ok,
                "provider": provider,
                "awaiting_human_batches": [b.batch_id for b in awaiting],
            }
        return {
            "step": None,
            "awaiting_human_batches": [b.batch_id for b in awaiting],
            "note": "No further auto-advance; check awaiting human selections or readiness gate.",
        }
