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
    PROMPT_COMPILER_VERSION,
    STYLE_MASTER_PROMPT,
    STYLE_MASTER_SEEDS,
    STYLE_NEGATIVE,
    STYLE_RECOVERY_DENOISE,
    STYLE_RECOVERY_NEGATIVE,
    STYLE_RECOVERY_PROMPT,
    STYLE_RECOVERY_PROMPT_VERSION,
    STYLE_RECOVERY_SEEDS,
    YARD_EMPTY_PROMPT,
)
from capos.core.errors import ValidationError
from capos.core.paths import project_root
from capos.core.schemas import CanonicalAssetRef, utcnow
from capos.core.status import CanonStatus, CanonStep
from capos.generation.capabilities import capability_matrix, select_production_provider
from capos.generation.concurrency import generation_slot
from capos.generation.image_validate import validate_candidate_image
from capos.generation.model_licence import load_model_provenance
from capos.generation.registry import _REGISTRY, record_provider_refusal
from capos.hardware.profile import load_hardware_profile, resolve_generation_settings
from capos.production.storage import ensure_production_tree, register_production_file
from capos.references.versioning import ReferenceStore

CANON_DEPENDENCIES: dict[CanonStep, list[str]] = {
    CanonStep.STYLE_MASTER: [],
    CanonStep.STYLE_RECOVERY: [],  # gated by VisualReferenceStore, not style-likkle-jay-v1
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
                        "Configure CAPOS_COMFYUI_URL (preferred), local Diffusers, or HF_TOKEN.",
                        "Mock art will not be accepted as production canon.",
                        "See docs/COMFYUI_LOCAL_SETUP.md for RTX 3050 6GB setup.",
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

        hw = resolve_generation_settings(load_hardware_profile(root=self.root))
        width = int(hw["width"])
        height = int(hw["height"])
        workflow = None
        if provider_name == "comfyui":
            import os

            workflow = os.environ.get(
                "CAPOS_COMFYUI_WORKFLOW", "style-master-toonyou-beta6.json"
            )

        # Deterministic seeds: style master uses permanent slot map; others use 1000+i
        seed_map: dict[str, int] = {}
        if step == CanonStep.STYLE_MASTER:
            for cid in list(STYLE_MASTER_SEEDS.keys())[:count]:
                seed_map[cid] = STYLE_MASTER_SEEDS[cid]
        else:
            for i in range(1, count + 1):
                seed_map[f"{batch_id}-c{i:03d}"] = 1000 + i

        candidates: list[CandidateAsset] = []
        notes: list[str] = []
        base_root = Path(self.root) if self.root else project_root()
        prov_model = load_model_provenance(root=self.root)
        for cid, seed in seed_map.items():
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
            with generation_slot(root=self.root):
                result = backend.generate_image(
                    prompt=prompt,
                    negative_prompt=negative,
                    width=width,
                    height=height,
                    seed=seed,
                    reference_images=refs or None,
                    output_path=out,
                    settings={
                        "capos_canon_step": step.value,
                        "non_production": non_prod,
                        "candidate_id": cid,
                        "batch_id": batch_id,
                        "workflow": workflow,
                        "steps": hw.get("steps_hint") or 20,
                        "cfg": hw.get("cfg_hint") or 7.0,
                        "sampler_name": "euler",
                        "scheduler": "normal",
                        "denoise": 1.0,
                    },
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
            validation = validate_candidate_image(Path(result.output_path), require_square=True)
            if not validation["ok"]:
                notes.append(f"{cid}: image validation failed — {validation.get('error')}")
                continue
            meta = register_production_file(
                series_id=self.series_id,
                category=category,
                asset_slug=slug,
                source_path=Path(result.output_path),
                root=self.root,
                kind="candidate",
            )
            gen_res = result.metadata.get("generation_resolution") or (
                f"{validation['width']}x{validation['height']}"
            )
            provenance = {
                "provider": result.metadata.get("provider") or f"{provider_name}-local",
                "checkpoint": result.metadata.get("checkpoint") or result.model,
                "model_family": result.metadata.get("model_family")
                or prov_model.get("architecture"),
                "model_licence_status": result.metadata.get("model_licence_status")
                or prov_model.get("licence_status"),
                "workflow": result.metadata.get("workflow") or workflow,
                "workflow_id": result.metadata.get("workflow_id"),
                "workflow_version": result.metadata.get("workflow_version"),
                "seed": seed,
                "positive_prompt": prompt,
                "negative_prompt": negative,
                "prompt_compiler_version": PROMPT_COMPILER_VERSION,
                "width": validation["width"],
                "height": validation["height"],
                "steps": result.metadata.get("steps"),
                "cfg": result.metadata.get("cfg"),
                "sampler_name": result.metadata.get("sampler_name"),
                "scheduler": result.metadata.get("scheduler"),
                "denoise": result.metadata.get("denoise"),
                "generated_at": utcnow().isoformat(),
                "duration_ms": result.metadata.get("duration_ms"),
                "checksum": validation["checksum"],
                "original_output_path": str(result.output_path),
            }
            qa = {
                "FILE_CHECK": "PASS",
                "DIMENSION_CHECK": "PASS",
                "SQUARE_CHECK": "PASS" if validation["square"] else "FAIL",
                "CHECKSUM": validation["checksum"],
                "VISUAL_IDENTITY": "REQUIRES_HUMAN_REVIEW",
                "non_production": non_prod,
                "images_claimed": True,
            }
            candidates.append(
                CandidateAsset(
                    candidate_id=cid,
                    file=meta["file"],
                    checksum=meta["checksum"],
                    backend=provider_name,
                    provider=str(provenance["provider"]),
                    model=result.model,
                    model_family=str(provenance["model_family"])
                    if provenance["model_family"]
                    else None,
                    model_licence_status=str(provenance["model_licence_status"])
                    if provenance["model_licence_status"]
                    else None,
                    seed=seed,
                    prompt_version=PROMPT_COMPILER_VERSION,
                    positive_prompt=prompt,
                    negative_prompt=negative,
                    workflow=str(provenance["workflow"]) if provenance["workflow"] else None,
                    workflow_id=provenance.get("workflow_id"),
                    workflow_version=str(provenance["workflow_version"])
                    if provenance.get("workflow_version")
                    else None,
                    generation_resolution=gen_res,
                    width=validation["width"],
                    height=validation["height"],
                    steps=provenance.get("steps"),
                    cfg=provenance.get("cfg"),
                    sampler_name=provenance.get("sampler_name"),
                    scheduler=provenance.get("scheduler"),
                    denoise=provenance.get("denoise"),
                    duration_ms=result.metadata.get("duration_ms"),
                    generated_at=str(provenance["generated_at"]),
                    original_output_path=str(result.output_path),
                    smoke_test=False,
                    qa_summary=qa,
                    provenance=provenance,
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

    def generate_style_recovery_candidates(
        self,
        *,
        count: int = 3,
        set_id: str = "likkle-jay-style-reference-set-v1",
    ) -> CandidateBatch:
        """Reference-grounded style recovery via img2img. Exactly 3 candidates when count=3.

        Requires approved style reference set. Does NOT generate character masters.
        """
        from capos.references.ingestion import VisualReferenceStore

        batch_id = "style-recovery-batch-001"
        vstore = VisualReferenceStore(self.series_id, root=self.root)
        gate = vstore.style_recovery_gate()
        if not gate["ready"]:
            batch = CandidateBatch(
                batch_id=batch_id,
                series_id=self.series_id,
                step=CanonStep.STYLE_RECOVERY,
                target_asset_id="style-likkle-jay-v1",
                status=CanonStatus.AWAITING_STYLE_REFERENCE_IMPORT,
                blocker=gate.get("stop") or "AWAITING_STYLE_REFERENCE_IMPORT",
                recommendation_notes=[
                    f"Import folder: {gate.get('import_folder')}",
                    str(gate.get("ui_action") or ""),
                    f"Preferred set: {gate.get('preferred_set_id')}",
                    "Approve 3–8 STYLE_REFERENCE images, create set, approve set, then regenerate.",
                ],
            )
            return self.batches.upsert(batch)

        ref_set = vstore.get_set(set_id)
        if not ref_set or ref_set.status != CanonStatus.APPROVED:
            approved = gate.get("approved_sets") or []
            if approved:
                set_id = approved[0]
                ref_set = vstore.get_set(set_id)
            if not ref_set or ref_set.status != CanonStatus.APPROVED:
                batch = CandidateBatch(
                    batch_id=batch_id,
                    series_id=self.series_id,
                    step=CanonStep.STYLE_RECOVERY,
                    target_asset_id="style-likkle-jay-v1",
                    status=CanonStatus.AWAITING_STYLE_REFERENCE_IMPORT,
                    blocker=f"Style reference set not approved: {set_id}",
                )
                return self.batches.upsert(batch)

        refs = []
        for rid in ref_set.reference_ids:
            ref = vstore.get(rid)
            if ref and Path(ref.file).is_file():
                refs.append(ref)
        if not refs:
            batch = CandidateBatch(
                batch_id=batch_id,
                series_id=self.series_id,
                step=CanonStep.STYLE_RECOVERY,
                target_asset_id="style-likkle-jay-v1",
                status=CanonStatus.AWAITING_STYLE_REFERENCE_IMPORT,
                blocker="Approved set has no readable reference files",
            )
            return self.batches.upsert(batch)

        ok, provider_or_reason = self.can_generate_production()
        if not ok:
            batch = CandidateBatch(
                batch_id=batch_id,
                series_id=self.series_id,
                step=CanonStep.STYLE_RECOVERY,
                target_asset_id="style-likkle-jay-v1",
                status=CanonStatus.BLOCKED_NO_PROVIDER,
                blocker=provider_or_reason,
                recommendation_notes=[
                    "Configure CAPOS_COMFYUI_URL + CAPOS_COMFYUI_CHECKPOINT for img2img recovery.",
                ],
            )
            return self.batches.upsert(batch)

        from capos.generation.registry import try_register_optional_backends

        try_register_optional_backends()
        if provider_or_reason not in _REGISTRY:
            batch = CandidateBatch(
                batch_id=batch_id,
                series_id=self.series_id,
                step=CanonStep.STYLE_RECOVERY,
                target_asset_id="style-likkle-jay-v1",
                status=CanonStatus.BLOCKED_NO_PROVIDER,
                blocker=f"Provider '{provider_or_reason}' not registered",
            )
            return self.batches.upsert(batch)

        backend = _REGISTRY[provider_or_reason]()
        if not backend.supports_edit():
            batch = CandidateBatch(
                batch_id=batch_id,
                series_id=self.series_id,
                step=CanonStep.STYLE_RECOVERY,
                target_asset_id="style-likkle-jay-v1",
                status=CanonStatus.BLOCKED_NO_PROVIDER,
                blocker=f"Provider '{provider_or_reason}' does not support IMAGE_TO_IMAGE",
            )
            return self.batches.upsert(batch)

        hw = resolve_generation_settings(load_hardware_profile(root=self.root))
        width = int(hw["width"])
        height = int(hw["height"])
        workflow = "style-recovery-img2img-low-vram.json"
        seed_map = dict(list(STYLE_RECOVERY_SEEDS.items())[:count])
        candidates: list[CandidateAsset] = []
        notes: list[str] = [
            f"Reference set: {set_id}",
            f"Conditioning: IMAGE_TO_IMAGE (denoise band {min(STYLE_RECOVERY_DENOISE.values())}"
            f"–{max(STYLE_RECOVERY_DENOISE.values())})",
            "Do not copy reference frames — generalise style only.",
            "Character production BLOCKED until style recovery approved.",
        ]
        base_root = Path(self.root) if self.root else project_root()
        prov_model = load_model_provenance(root=self.root)

        for idx, (cid, seed) in enumerate(seed_map.items()):
            ref = refs[idx % len(refs)]
            denoise = STYLE_RECOVERY_DENOISE.get(cid, 0.45)
            out = (
                base_root
                / "production"
                / self.series_id
                / "candidates"
                / "style"
                / "style-recovery"
                / f"{cid}.png"
            )
            out.parent.mkdir(parents=True, exist_ok=True)
            with generation_slot(root=self.root):
                result = backend.edit_image(
                    source_image=ref.file,
                    prompt=STYLE_RECOVERY_PROMPT,
                    negative_prompt=STYLE_RECOVERY_NEGATIVE,
                    output_path=out,
                    settings={
                        "seed": seed,
                        "workflow": workflow,
                        "steps": hw.get("steps_hint") or 20,
                        "cfg": hw.get("cfg_hint") or 7.0,
                        "sampler_name": "euler",
                        "scheduler": "normal",
                        "denoise": denoise,
                        "force_width": width,
                        "force_height": height,
                        "candidate_id": cid,
                        "batch_id": batch_id,
                        "capos_canon_step": CanonStep.STYLE_RECOVERY.value,
                    },
                )
            if result.refusal:
                record_provider_refusal(
                    backend=provider_or_reason,
                    prompt=STYLE_RECOVERY_PROMPT,
                    refusal=result.refusal,
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
            validation = validate_candidate_image(Path(result.output_path), require_square=True)
            if not validation["ok"]:
                notes.append(f"{cid}: image validation failed — {validation.get('error')}")
                continue
            meta = register_production_file(
                series_id=self.series_id,
                category="style",
                asset_slug="style-recovery",
                source_path=Path(result.output_path),
                root=self.root,
                kind="candidate",
            )
            gen_res = result.metadata.get("generation_resolution") or (
                f"{validation['width']}x{validation['height']}"
            )
            provenance = {
                "provider": result.metadata.get("provider") or f"{provider_or_reason}-local",
                "checkpoint": result.metadata.get("checkpoint") or result.model,
                "model_family": result.metadata.get("model_family")
                or prov_model.get("architecture"),
                "model_licence_status": result.metadata.get("model_licence_status")
                or prov_model.get("licence_status"),
                "workflow": result.metadata.get("workflow") or workflow,
                "workflow_id": result.metadata.get("workflow_id"),
                "workflow_version": result.metadata.get("workflow_version"),
                "seed": seed,
                "positive_prompt": STYLE_RECOVERY_PROMPT,
                "negative_prompt": STYLE_RECOVERY_NEGATIVE,
                "prompt_compiler_version": STYLE_RECOVERY_PROMPT_VERSION,
                "conditioning_method": "IMAGE_TO_IMAGE",
                "conditioning_strength": denoise,
                "denoise": denoise,
                "reference_set_id": set_id,
                "reference_ids": [ref.reference_id],
                "reference_checksums": [ref.checksum],
                "width": validation["width"],
                "height": validation["height"],
                "steps": result.metadata.get("steps"),
                "cfg": result.metadata.get("cfg"),
                "sampler_name": result.metadata.get("sampler_name"),
                "scheduler": result.metadata.get("scheduler"),
                "generated_at": utcnow().isoformat(),
                "duration_ms": result.metadata.get("duration_ms"),
                "checksum": validation["checksum"],
                "original_output_path": str(result.output_path),
            }
            qa = {
                "FILE_CHECK": "PASS",
                "DIMENSION_CHECK": "PASS",
                "SQUARE_CHECK": "PASS" if validation["square"] else "FAIL",
                "CHECKSUM": validation["checksum"],
                "VISUAL_IDENTITY": "REQUIRES_HUMAN_REVIEW",
                "STYLE_RECOVERY": "REQUIRES_HUMAN_REVIEW",
                "identity_claim": False,
                "images_claimed": True,
                "human_review_categories": [
                    "LINEWORK_MATCH",
                    "SHAPE_LANGUAGE_MATCH",
                    "COLOUR_LANGUAGE_MATCH",
                    "SHADING_MATCH",
                    "FACE_STYLE_MATCH",
                    "BACKGROUND_STYLE_MATCH",
                    "COMEDY_EXPRESSIVENESS",
                    "ANIME_DRIFT",
                    "PHOTOREALISM_DRIFT",
                    "OVER_DETAILING",
                    "OVERALL_CONTINUITY",
                ],
            }
            candidates.append(
                CandidateAsset(
                    candidate_id=cid,
                    file=meta["file"],
                    checksum=meta["checksum"],
                    backend=provider_or_reason,
                    provider=str(provenance["provider"]),
                    model=result.model,
                    model_family=str(provenance["model_family"])
                    if provenance["model_family"]
                    else None,
                    model_licence_status=str(provenance["model_licence_status"])
                    if provenance["model_licence_status"]
                    else None,
                    seed=seed,
                    prompt_version=STYLE_RECOVERY_PROMPT_VERSION,
                    positive_prompt=STYLE_RECOVERY_PROMPT,
                    negative_prompt=STYLE_RECOVERY_NEGATIVE,
                    workflow=str(provenance["workflow"]),
                    workflow_id=provenance.get("workflow_id"),
                    workflow_version=str(provenance["workflow_version"])
                    if provenance.get("workflow_version")
                    else None,
                    generation_resolution=gen_res,
                    width=validation["width"],
                    height=validation["height"],
                    steps=provenance.get("steps"),
                    cfg=provenance.get("cfg"),
                    sampler_name=provenance.get("sampler_name"),
                    scheduler=provenance.get("scheduler"),
                    denoise=denoise,
                    duration_ms=result.metadata.get("duration_ms"),
                    generated_at=str(provenance["generated_at"]),
                    original_output_path=str(result.output_path),
                    smoke_test=False,
                    qa_summary=qa,
                    provenance=provenance,
                    status=CanonStatus.CANDIDATE,
                    non_production=False,
                    batch_kind="style_recovery",
                    conditioning_method="IMAGE_TO_IMAGE",
                    conditioning_strength=denoise,
                    reference_set_id=set_id,
                    reference_ids=[ref.reference_id],
                    reference_checksums=[ref.checksum],
                )
            )

        status = (
            CanonStatus.AWAITING_HUMAN_STYLE_RECOVERY_REVIEW
            if candidates
            else CanonStatus.BLOCKED_NO_PROVIDER
        )
        batch = CandidateBatch(
            batch_id=batch_id,
            series_id=self.series_id,
            step=CanonStep.STYLE_RECOVERY,
            target_asset_id="style-likkle-jay-v1",
            parent_asset_ids=[],
            status=status,
            candidates=candidates,
            recommendation_notes=notes,
            blocker=None if candidates else "No successful style recovery outputs",
        )
        return self.batches.upsert(batch)

    def regenerate_style_same_seed(self, candidate_id: str) -> CandidateBatch:
        """Regenerate one style slot with the same permanent seed; keep prior as history."""
        if candidate_id not in STYLE_MASTER_SEEDS:
            raise ValidationError(
                f"Unknown style candidate slot {candidate_id}",
                hint=f"Expected one of {list(STYLE_MASTER_SEEDS)}",
            )
        seed = STYLE_MASTER_SEEDS[candidate_id]
        batch = self.batches.get("style-master-batch-001")
        prior = None
        if batch:
            prior = next((c for c in batch.candidates if c.candidate_id == candidate_id), None)

        ok, provider_or_reason = self.can_generate_production()
        if not ok:
            raise ValidationError(provider_or_reason)
        from capos.generation.registry import try_register_optional_backends

        try_register_optional_backends()
        backend = _REGISTRY[provider_or_reason]()
        hw = resolve_generation_settings(load_hardware_profile(root=self.root))
        import os

        workflow = os.environ.get("CAPOS_COMFYUI_WORKFLOW", "style-master-toonyou-beta6.json")
        stamp = utcnow().strftime("%Y%m%dT%H%M%SZ")
        new_id = f"{candidate_id}-r{stamp}"
        base_root = Path(self.root) if self.root else project_root()
        out = (
            base_root
            / "production"
            / self.series_id
            / "candidates"
            / "style"
            / "style-master"
            / f"{new_id}.png"
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        with generation_slot(root=self.root):
            result = backend.generate_image(
                prompt=STYLE_MASTER_PROMPT,
                negative_prompt=STYLE_NEGATIVE,
                width=hw["width"],
                height=hw["height"],
                seed=seed,
                output_path=out,
                settings={
                    "candidate_id": new_id,
                    "workflow": workflow,
                    "steps": 20,
                    "cfg": 7.0,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                },
            )
        if not result.success or not result.output_path:
            raise ValidationError(result.error or "regeneration failed")
        validation = validate_candidate_image(Path(result.output_path))
        if not validation["ok"]:
            raise ValidationError(str(validation.get("error")))
        meta = register_production_file(
            series_id=self.series_id,
            category="style",
            asset_slug="style-master",
            source_path=Path(result.output_path),
            root=self.root,
            kind="candidate",
        )
        prov_model = load_model_provenance(root=self.root)
        new_cand = CandidateAsset(
            candidate_id=new_id,
            file=meta["file"],
            checksum=meta["checksum"],
            backend=provider_or_reason,
            provider="comfyui-local",
            model=result.model,
            model_family=prov_model.get("architecture"),
            model_licence_status=prov_model.get("licence_status"),
            seed=seed,
            prompt_version=PROMPT_COMPILER_VERSION,
            positive_prompt=STYLE_MASTER_PROMPT,
            negative_prompt=STYLE_NEGATIVE,
            workflow=workflow,
            generation_resolution=f"{validation['width']}x{validation['height']}",
            width=validation["width"],
            height=validation["height"],
            steps=result.metadata.get("steps"),
            cfg=result.metadata.get("cfg"),
            sampler_name=result.metadata.get("sampler_name"),
            scheduler=result.metadata.get("scheduler"),
            denoise=result.metadata.get("denoise"),
            duration_ms=result.metadata.get("duration_ms"),
            generated_at=utcnow().isoformat(),
            original_output_path=str(result.output_path),
            regenerates=candidate_id,
            qa_summary={
                "FILE_CHECK": "PASS",
                "DIMENSION_CHECK": "PASS",
                "CHECKSUM": validation["checksum"],
                "VISUAL_IDENTITY": "REQUIRES_HUMAN_REVIEW",
                "images_claimed": True,
                "regen_mode": "SAME_SEED",
            },
            provenance={
                "regen_mode": "SAME_SEED",
                "prior_candidate_id": candidate_id,
                "seed": seed,
                "checksum": validation["checksum"],
            },
            status=CanonStatus.CANDIDATE,
        )
        if not batch:
            batch = CandidateBatch(
                batch_id="style-master-batch-001",
                series_id=self.series_id,
                step=CanonStep.STYLE_MASTER,
                target_asset_id="style-likkle-jay-v1",
                status=CanonStatus.AWAITING_HUMAN_SELECTION,
                candidates=[],
            )
        if prior:
            prior.status = CanonStatus.REJECTED
            prior.superseded_by = new_id
        batch.candidates = [c for c in batch.candidates if c.candidate_id != new_id]
        batch.candidates.append(new_cand)
        batch.status = CanonStatus.AWAITING_HUMAN_SELECTION
        batch.recommendation_notes.append(
            f"SAME_SEED regen: {candidate_id} → {new_id} (seed={seed}); prior kept as REJECTED."
        )
        return self.batches.upsert(batch)

    def create_new_style_candidate(self, *, seed: int | None = None) -> CandidateBatch:
        """Create an additional style candidate with a new seed; never overwrite existing slots."""
        import secrets

        new_seed = int(seed) if seed is not None else secrets.randbelow(2_147_483_647) + 1
        stamp = utcnow().strftime("%Y%m%dT%H%M%SZ")
        cid = f"style-master-candidate-extra-{stamp}"
        ok, provider_or_reason = self.can_generate_production()
        if not ok:
            raise ValidationError(provider_or_reason)
        from capos.generation.registry import try_register_optional_backends

        try_register_optional_backends()
        backend = _REGISTRY[provider_or_reason]()
        hw = resolve_generation_settings(load_hardware_profile(root=self.root))
        import os

        workflow = os.environ.get("CAPOS_COMFYUI_WORKFLOW", "style-master-toonyou-beta6.json")
        base_root = Path(self.root) if self.root else project_root()
        out = (
            base_root
            / "production"
            / self.series_id
            / "candidates"
            / "style"
            / "style-master"
            / f"{cid}.png"
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        with generation_slot(root=self.root):
            result = backend.generate_image(
                prompt=STYLE_MASTER_PROMPT,
                negative_prompt=STYLE_NEGATIVE,
                width=hw["width"],
                height=hw["height"],
                seed=new_seed,
                output_path=out,
                settings={
                    "candidate_id": cid,
                    "workflow": workflow,
                    "steps": 20,
                    "cfg": 7.0,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                },
            )
        if not result.success or not result.output_path:
            raise ValidationError(result.error or "new candidate failed")
        validation = validate_candidate_image(Path(result.output_path))
        if not validation["ok"]:
            raise ValidationError(str(validation.get("error")))
        meta = register_production_file(
            series_id=self.series_id,
            category="style",
            asset_slug="style-master",
            source_path=Path(result.output_path),
            root=self.root,
            kind="candidate",
        )
        batch = self.batches.get("style-master-batch-001") or CandidateBatch(
            batch_id="style-master-batch-001",
            series_id=self.series_id,
            step=CanonStep.STYLE_MASTER,
            target_asset_id="style-likkle-jay-v1",
            status=CanonStatus.AWAITING_HUMAN_SELECTION,
            candidates=[],
        )
        batch.candidates.append(
            CandidateAsset(
                candidate_id=cid,
                file=meta["file"],
                checksum=meta["checksum"],
                backend=provider_or_reason,
                provider="comfyui-local",
                model=result.model,
                seed=new_seed,
                prompt_version=PROMPT_COMPILER_VERSION,
                positive_prompt=STYLE_MASTER_PROMPT,
                negative_prompt=STYLE_NEGATIVE,
                workflow=workflow,
                generation_resolution=f"{validation['width']}x{validation['height']}",
                width=validation["width"],
                height=validation["height"],
                duration_ms=result.metadata.get("duration_ms"),
                generated_at=utcnow().isoformat(),
                original_output_path=str(result.output_path),
                qa_summary={
                    "FILE_CHECK": "PASS",
                    "CHECKSUM": validation["checksum"],
                    "VISUAL_IDENTITY": "REQUIRES_HUMAN_REVIEW",
                    "images_claimed": True,
                    "regen_mode": "NEW_SEED",
                },
                provenance={"regen_mode": "NEW_SEED", "seed": new_seed},
                status=CanonStatus.CANDIDATE,
            )
        )
        batch.status = CanonStatus.AWAITING_HUMAN_SELECTION
        batch.recommendation_notes.append(f"NEW_CANDIDATE {cid} seed={new_seed}")
        return self.batches.upsert(batch)

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
        from capos.references.ingestion import VisualReferenceStore

        awaiting = self.batches.awaiting_human()
        recovery = self.batches.get("style-recovery-batch-001")
        if recovery and recovery.status == CanonStatus.AWAITING_HUMAN_STYLE_RECOVERY_REVIEW:
            return {
                "step": CanonStep.STYLE_RECOVERY.value,
                "status": recovery.status.value,
                "stop": "AWAITING_HUMAN_STYLE_RECOVERY_REVIEW",
                "batch_id": recovery.batch_id,
                "candidate_count": len(recovery.candidates),
                "note": "Human must review style recovery candidates before character production.",
            }

        # Style not locked → prefer recovery path over text-only invention
        if not _approved_with_file(self.store, "style-likkle-jay-v1"):
            gate = VisualReferenceStore(self.series_id, root=self.root).style_recovery_gate()
            phase2a = self.batches.get("style-master-batch-001")
            phase2a_rejected = bool(
                phase2a and phase2a.status == CanonStatus.HUMAN_REJECTED_STYLE_DRIFT
            )
            if not gate["ready"]:
                return {
                    "step": CanonStep.STYLE_RECOVERY.value,
                    "status": CanonStatus.AWAITING_STYLE_REFERENCE_IMPORT.value,
                    "stop": "AWAITING_STYLE_REFERENCE_IMPORT",
                    "phase2a_rejected": phase2a_rejected,
                    "import_folder": gate.get("import_folder"),
                    "ui_action": gate.get("ui_action"),
                    "preferred_set_id": gate.get("preferred_set_id"),
                    "provider_ok": self.can_generate_production()[0],
                }
            return {
                "step": CanonStep.STYLE_RECOVERY.value,
                "status": "READY_FOR_RECOVERY_GENERATION",
                "stop": None,
                "approved_sets": gate.get("approved_sets"),
                "provider_ok": self.can_generate_production()[0],
                "note": "Run generate_style_recovery_candidates (×3) then human review.",
            }

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
