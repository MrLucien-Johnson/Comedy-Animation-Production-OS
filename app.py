"""CAPOS Production UI — Streamlit dashboard with Canon workflow."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from capos import __version__
from capos.canon.bootstrap import bootstrap_likkle_jay_canon
from capos.canon.candidates import CandidateStore
from capos.canon.diff import compare_to_canon, compare_to_reference
from capos.canon.pipeline import CanonCreationPipeline
from capos.canon.style_rejection import reject_phase2a_style_drift
from capos.core.paths import project_root, series_dir
from capos.core.schemas import WATERMARK_EXACT
from capos.core.status import CanonStatus, CanonStep, StageStatus, VisualReferenceType
from capos.domain.series import (
    list_series,
    load_episode_brief,
    load_script,
    load_series,
    load_storyboard,
)
from capos.export.ffmpeg_export import ffmpeg_available
from capos.generation.capabilities import capability_matrix, select_production_provider
from capos.generation.provider_status import provider_dashboard_status
from capos.generation.registry import try_register_optional_backends
from capos.pipeline.readiness import evaluate_season_production_ready
from capos.references.golden import GoldenFrameStore
from capos.references.ingestion import VisualReferenceStore
from capos.references.versioning import ReferenceStore

st.set_page_config(page_title="CAPOS", layout="wide")
st.title("Comedy Animation Production OS")
st.caption(f"v{__version__} · watermark `{WATERMARK_EXACT}`")

try_register_optional_backends()
root = project_root()

nav = st.sidebar.radio(
    "Navigate",
    [
        "Dashboard",
        "Series",
        "Canon",
        "Canon Candidates",
        "Compare to Canon",
        "Compare to Reference",
        "Characters",
        "Locations",
        "Props",
        "Episodes",
        "Script",
        "Storyboard",
        "References",
        "Golden Frames",
        "Frames / Continuity",
        "QA",
        "Providers",
        "Readiness Gate",
        "Animation",
        "Audio",
        "Exports",
    ],
)

series_ids = list_series(root=root)
series_id = st.sidebar.selectbox("Series", series_ids or ["likkle-jay"])


def _status_badge(status: object) -> str:
    return status.value if hasattr(status, "value") else str(status)


if nav == "Dashboard":
    st.subheader("Production dashboard")
    report = evaluate_season_production_ready(series_id, root=root)
    cols = st.columns(5)
    cols[0].metric("Series", len(series_ids))
    cols[1].metric("FFmpeg", "yes" if ffmpeg_available()[0] else "no")
    cols[2].metric("Engineering", "ready" if report.engineering_ready else "no")
    cols[3].metric("Content", "ready" if report.content_ready else "NOT READY")
    cols[4].metric("Season gate", "PASS" if report.season_production_ready else "FAIL")
    st.write("Provider availability:")
    st.json(provider_dashboard_status())
    st.write("Production provider selection:")
    st.json(select_production_provider())
    st.info(
        "Do not mass-generate episodes until SEASON_PRODUCTION_READY passes. "
        "Canon → Approval → Golden references → Production. "
        "Mock art is never production canon."
    )

elif nav == "Series":
    st.subheader("Series")
    if (series_dir(series_id, root=root) / "series.json").is_file():
        st.json(load_series(series_id, root=root).model_dump())
        bible = series_dir(series_id, root=root) / "BIBLE.md"
        if bible.is_file():
            st.markdown(bible.read_text())

elif nav == "Canon":
    st.subheader("Canonical production registry")
    if st.button("Bootstrap / refresh Likkle Jay canon metadata"):
        result = bootstrap_likkle_jay_canon(root=root)
        st.success(result["note"])
        st.json({k: result[k] for k in result if k != "registry_entries"})
        st.caption(f"{len(result['registry_entries'])} registry entries")
    store = ReferenceStore(series_id, root=root)
    assets = store.list_assets()
    st.write(f"{len(assets)} assets")
    for a in assets:
        with st.expander(f"{a.asset_id} · {_status_badge(a.status)}"):
            cols = st.columns([1, 2])
            if a.effective_path and Path(a.effective_path).is_file():
                cols[0].image(a.effective_path, use_container_width=True)
            else:
                cols[0].warning("No image file — not claimable as production art")
            cols[1].json(
                {
                    "type": _status_badge(a.type) if a.type else a.kind,
                    "version": a.version,
                    "status": _status_badge(a.status),
                    "source": a.source,
                    "file": a.effective_path,
                    "checksum": a.checksum,
                    "reference_required": a.reference_required,
                    "locked_traits": a.locked_traits,
                }
            )
            c1, c2, c3, c4 = st.columns(4)
            if c1.button("APPROVE", key=f"ap_{a.asset_id}"):
                try:
                    store.approve(a.asset_id)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            if c2.button("REJECT", key=f"rj_{a.asset_id}"):
                store.reject(a.asset_id)
                st.rerun()
            if c3.button("LOCK AS CANON", key=f"lk_{a.asset_id}"):
                try:
                    store.lock_as_canon(a.asset_id)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            upload = c4.file_uploader(
                "Import image", type=["png", "jpg", "webp"], key=f"up_{a.asset_id}"
            )
            if upload is not None:
                dest = (
                    series_dir(series_id, root=root)
                    / "references"
                    / "imports"
                    / a.asset_id
                    / upload.name
                )
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(upload.getvalue())
                store.attach_file(a.asset_id, dest, source="user_upload")
                st.success(f"Attached {dest.name} as CANDIDATE")
                st.rerun()

elif nav == "Canon Candidates":
    st.subheader("Canon Candidates — human selection required")
    pipe = CanonCreationPipeline(series_id, root=root)
    next_step = pipe.next_actionable_step()
    st.json(next_step)
    if next_step.get("stop") == "AWAITING_STYLE_REFERENCE_IMPORT":
        st.warning(
            "Phase 2B stop: import & approve Likkle Jay style references before recovery generation."
        )
        st.code(next_step.get("import_folder") or "")
        st.info(next_step.get("ui_action") or "")
    if next_step.get("stop") == "AWAITING_HUMAN_STYLE_RECOVERY_REVIEW":
        st.success("Style recovery candidates awaiting human review — do not generate characters yet.")

    if st.button("Mark Phase 2A style candidates REJECTED (style drift)"):
        st.json(reject_phase2a_style_drift(series_id, root=root))
        st.rerun()

    c1, c2, c3, c4 = st.columns(4)
    if c1.button("Generate STYLE candidates (×3) [Phase 2A — deprecated]"):
        batch = pipe.generate_style_candidates(count=3)
        st.write(batch.model_dump())
        st.rerun()
    if c2.button("Generate STYLE RECOVERY (×3) [Phase 2B]"):
        st.write(pipe.generate_style_recovery_candidates(count=3).model_dump())
        st.rerun()
    if c3.button("Generate LIKKLE JAY candidates (×3)"):
        st.warning("Character production blocked until style recovery approved.")
        st.write(pipe.generate_likkle_jay_candidates(count=3).model_dump())
        st.rerun()
    if c4.button("Generate AUNTIE BEV candidates (×3)"):
        st.warning("Character production blocked until style recovery approved.")
        st.write(pipe.generate_auntie_bev_candidates(count=3).model_dump())
        st.rerun()
    loc_cols = st.columns(4)
    for i, loc in enumerate(["kitchen", "living-room", "yard", "bedroom"]):
        if loc_cols[i].button(f"Gen {loc}"):
            st.write(pipe.generate_location_candidates(loc, count=3).model_dump())
            st.rerun()
    if st.button("Generate COOKIE JAR candidates (×3)"):
        st.write(pipe.generate_cookie_jar_candidates(count=3).model_dump())
        st.rerun()

    store_b = CandidateStore(series_id, root=root)
    all_batches = store_b.list_batches()
    rejected_ids = {
        b.batch_id
        for b in all_batches
        if b.status == CanonStatus.HUMAN_REJECTED_STYLE_DRIFT
        or b.batch_id == "style-master-batch-001"
    }
    recovery_ids = {
        b.batch_id
        for b in all_batches
        if b.step == CanonStep.STYLE_RECOVERY
        or (b.candidates and any(c.batch_kind == "style_recovery" for c in b.candidates))
    }
    rejected_batches = [b for b in all_batches if b.batch_id in rejected_ids]
    recovery_batches = [
        b for b in all_batches if b.batch_id in recovery_ids and b.batch_id not in rejected_ids
    ]
    other_batches = [
        b
        for b in all_batches
        if b.batch_id not in rejected_ids and b.batch_id not in recovery_ids
    ]

    st.markdown("### Rejected Phase 2A candidates (do not select as canon)")
    for batch in rejected_batches:
        with st.expander(
            f"{batch.batch_id} · {_status_badge(batch.status)} → {batch.target_asset_id}",
            expanded=False,
        ):
            if batch.blocker:
                st.error(batch.blocker)
            st.write(batch.recommendation_notes)
            cols = st.columns(max(len(batch.candidates) or 1, 1))
            for idx, cand in enumerate(batch.candidates):
                with cols[idx % len(cols)]:
                    st.markdown(f"**{cand.candidate_id}** · `{_status_badge(cand.status)}`")
                    if cand.file and Path(cand.file).is_file():
                        st.image(cand.file, use_container_width=True)
                    st.caption(f"rejection: {cand.rejection_code or cand.rejection_reason}")
                    st.info("SELECT disabled — HUMAN_REJECTED_STYLE_DRIFT")

    st.markdown("### Reference-grounded style recovery candidates")
    for batch in recovery_batches:
        with st.expander(
            f"{batch.batch_id} · {_status_badge(batch.status)} → {batch.target_asset_id}",
            expanded=True,
        ):
            if batch.blocker:
                st.error(batch.blocker)
            st.write(batch.recommendation_notes)
            active = list(batch.candidates)
            cols = st.columns(max(len(active), 1))
            for idx, cand in enumerate(active):
                col = cols[idx % len(cols)]
                with col:
                    st.markdown(f"**{cand.candidate_id}**")
                    if cand.file and Path(cand.file).is_file():
                        st.image(cand.file, use_container_width=True)
                    else:
                        st.warning("No file")
                    st.caption(
                        f"checkpoint: `{cand.model}` · seed: `{cand.seed}` · "
                        f"denoise: `{cand.denoise}` · {cand.conditioning_method}"
                    )
                    st.json(
                        {
                            "reference_set_id": cand.reference_set_id,
                            "reference_ids": cand.reference_ids,
                            "reference_checksums": cand.reference_checksums,
                            "qa": cand.qa_summary,
                            "workflow": cand.workflow,
                        }
                    )
                    if st.button("SELECT", key=f"sel_{batch.batch_id}_{cand.candidate_id}"):
                        try:
                            pipe.promote_selection_to_canon(batch.batch_id, cand.candidate_id)
                            st.success(
                                f"Selected {cand.candidate_id}. APPROVE on Canon page to lock."
                            )
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))
                    if st.button("REJECT", key=f"rej_{batch.batch_id}_{cand.candidate_id}"):
                        cand.status = CanonStatus.REJECTED
                        store_b.upsert(batch)
                        st.rerun()

    st.markdown("### Other candidate batches")
    for batch in other_batches:
        with st.expander(
            f"{batch.batch_id} · {_status_badge(batch.status)} → {batch.target_asset_id}",
            expanded=False,
        ):
            if batch.blocker:
                st.error(batch.blocker)
            st.write(batch.recommendation_notes)
            active = [c for c in batch.candidates if c.status != CanonStatus.REJECTED]
            if not active:
                active = list(batch.candidates)
            cols = st.columns(max(len(active), 1))
            for idx, cand in enumerate(active):
                col = cols[idx % len(cols)]
                with col:
                    st.markdown(f"**{cand.candidate_id}**")
                    if cand.file and Path(cand.file).is_file():
                        st.image(cand.file, use_container_width=True)
                    else:
                        st.warning("No file")
                    st.caption(
                        f"checkpoint: `{cand.model}` · seed: `{cand.seed}` · "
                        f"{cand.generation_resolution} · {cand.duration_ms} ms"
                    )
                    st.json(
                        {
                            "qa": cand.qa_summary,
                            "licence": cand.model_licence_status,
                            "workflow": cand.workflow,
                            "provider": cand.provider,
                        }
                    )
                    if cand.smoke_test or cand.non_production:
                        st.warning("NON-PRODUCTION / SMOKE — cannot lock as canon")
                        continue
                    if cand.status == CanonStatus.HUMAN_REJECTED_STYLE_DRIFT or cand.qa_summary.get(
                        "do_not_select_as_canon"
                    ):
                        st.info("SELECT disabled — rejected for style drift")
                        continue
                    if st.button("SELECT", key=f"sel_{batch.batch_id}_{cand.candidate_id}"):
                        try:
                            pipe.promote_selection_to_canon(batch.batch_id, cand.candidate_id)
                            st.success(
                                f"Selected {cand.candidate_id}. APPROVE on Canon page to lock."
                            )
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))
                    if st.button("REJECT", key=f"rej_{batch.batch_id}_{cand.candidate_id}"):
                        cand.status = CanonStatus.REJECTED
                        store_b.upsert(batch)
                        st.rerun()
                    if cand.candidate_id.startswith("style-master-candidate-00") or (
                        cand.seed is not None and "style-master" in cand.candidate_id
                    ):
                        if st.button(
                            "REGENERATE SAME SEED",
                            key=f"rs_{batch.batch_id}_{cand.candidate_id}",
                        ):
                            try:
                                slot = cand.regenerates or cand.candidate_id
                                if slot not in {
                                    "style-master-candidate-001",
                                    "style-master-candidate-002",
                                    "style-master-candidate-003",
                                }:
                                    slot = cand.candidate_id.split("-r")[0]
                                st.write(pipe.regenerate_style_same_seed(slot).model_dump())
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))
            if batch.step == CanonStep.STYLE_MASTER or (
                hasattr(batch.step, "value") and batch.step.value == "STYLE_MASTER"
            ):
                if st.button("NEW CANDIDATE (new seed)", key=f"new_{batch.batch_id}"):
                    try:
                        st.write(pipe.create_new_style_candidate().model_dump())
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
elif nav == "Compare to Canon":
    st.subheader("COMPARE TO CANON")
    parent_id = st.text_input("Parent / approved asset id", "style-likkle-jay-v1")
    cand_path = st.text_input("Candidate image path (optional)")
    if st.button("Compare"):
        st.json(
            compare_to_canon(
                series_id=series_id,
                candidate_file=cand_path or None,
                parent_asset_id=parent_id or None,
                root=root,
            )
        )

elif nav == "Compare to Reference":
    st.subheader("COMPARE TO REFERENCE — style recovery QA")
    st.caption("Human review is authoritative. No fake semantic identity score.")
    vstore = VisualReferenceStore(series_id, root=root)
    sets = vstore.list_sets()
    set_ids = [s.set_id for s in sets] or ["likkle-jay-style-reference-set-v1"]
    ref_set = st.selectbox("Style reference set", set_ids)
    refs = vstore.list_references(reference_type=VisualReferenceType.STYLE_REFERENCE)
    ref_ids = ["(entire set)"] + [r.reference_id for r in refs]
    pick = st.selectbox("Single reference (optional)", ref_ids)
    cand_path = st.text_input("Recovery candidate image path")
    if cand_path and Path(cand_path).is_file():
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**REFERENCE(S)**")
            show_refs = refs if pick == "(entire set)" else [r for r in refs if r.reference_id == pick]
            for r in show_refs:
                if Path(r.file).is_file():
                    st.image(r.file, caption=f"{r.reference_id} · {r.checksum[:12]}…")
        with c2:
            st.markdown("**GENERATED CANDIDATE**")
            st.image(cand_path)
    if st.button("Run compare to reference"):
        report = compare_to_reference(
            series_id=series_id,
            candidate_file=cand_path or None,
            reference_id=None if pick == "(entire set)" else pick,
            reference_set_id=ref_set if pick == "(entire set)" else None,
            root=root,
        )
        st.json(report)
        st.markdown("**Human review categories**")
        for cat in report.get("human_review_categories") or []:
            st.checkbox(cat, key=f"hr_{cat}", value=False)

elif nav == "Characters":
    st.subheader("Characters")
    store = ReferenceStore(series_id, root=root)
    for a in store.list_assets():
        if a.kind in {"character", "turnaround", "expression", "outfit"} or (
            a.type and ("CHARACTER" in _status_badge(a.type) or "OUTFIT" in _status_badge(a.type))
        ):
            st.write(f"`{a.asset_id}` — {_status_badge(a.status)} — file={a.effective_path}")

elif nav == "Locations":
    st.subheader("Locations")
    store = ReferenceStore(series_id, root=root)
    for a in store.list_assets(kind="location"):
        st.write(f"`{a.asset_id}` — {_status_badge(a.status)}")
    spatial = series_dir(series_id, root=root) / "spatial"
    if spatial.is_dir():
        for f in sorted(spatial.glob("*.json")):
            st.markdown(f"**Spatial:** {f.stem}")
            st.json(json.loads(f.read_text()))

elif nav == "Props":
    st.subheader("Props")
    store = ReferenceStore(series_id, root=root)
    for a in store.list_assets():
        if a.kind in {"prop", "prop-state"}:
            st.write(f"`{a.asset_id}` — {_status_badge(a.status)} — {a.metadata}")

elif nav == "Episodes":
    st.subheader("Episodes")
    ep_root = series_dir(series_id, root=root) / "episodes"
    if ep_root.is_dir():
        for ep in sorted(p.name for p in ep_root.iterdir() if p.is_dir()):
            brief = load_episode_brief(series_id, ep, root=root)
            st.markdown(f"### {brief.title} (`{ep}`)")
            st.write(f"Status: **{brief.status}** — {brief.premise}")

elif nav == "Script":
    ep = st.selectbox("Episode", ["s01e01", "s01e02", "s01e03"])
    st.json(load_script(series_id, ep, root=root).model_dump())

elif nav == "Storyboard":
    ep = st.selectbox("Episode", ["s01e01", "s01e02", "s01e03"], key="sb")
    st.json([b.model_dump() for b in load_storyboard(series_id, ep, root=root)])

elif nav == "References":
    st.subheader("Visual references — import established artwork")
    vstore = VisualReferenceStore(series_id, root=root)
    gate = vstore.style_recovery_gate()
    st.json(gate)
    st.markdown("### Import Visual Reference")
    ref_type = st.selectbox(
        "Reference type",
        [t.value for t in VisualReferenceType],
        index=0,
    )
    notes = st.text_input("Notes / provenance", "")
    upload = st.file_uploader(
        "Import image (PNG / JPG / WEBP)",
        type=["png", "jpg", "jpeg", "webp"],
        key="vis_ref_upload",
    )
    custom_id = st.text_input("Optional reference ID", "")
    if upload is not None and st.button("IMPORT REFERENCE"):
        dest = (
            series_dir(series_id, root=root)
            / "visual_references"
            / "_staging"
            / upload.name
        )
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(upload.getvalue())
        try:
            ref = vstore.import_reference(
                dest,
                reference_type=VisualReferenceType(ref_type),
                reference_id=custom_id or None,
                notes=notes,
                source="streamlit_import",
            )
            st.success(f"Imported {ref.reference_id} · checksum {ref.checksum[:16]}…")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    st.markdown("### Imported references")
    for ref in vstore.list_references():
        with st.expander(f"{ref.reference_id} · {_status_badge(ref.status)} · {ref.reference_type.value}"):
            cols = st.columns([1, 2])
            if Path(ref.file).is_file():
                cols[0].image(ref.file, use_container_width=True)
            cols[1].json(
                {
                    "checksum": ref.checksum,
                    "dimensions": f"{ref.width}x{ref.height}",
                    "imported_at": ref.imported_at,
                    "source": ref.source,
                    "notes": ref.notes,
                    "provenance": ref.provenance,
                    "file": ref.file,
                }
            )
            if ref.status != CanonStatus.APPROVED and st.button(
                "APPROVE REFERENCE", key=f"aref_{ref.reference_id}"
            ):
                vstore.approve_reference(ref.reference_id)
                st.rerun()

    st.markdown("### Style reference sets")
    approved_ids = [
        r.reference_id
        for r in vstore.list_references(reference_type=VisualReferenceType.STYLE_REFERENCE)
        if r.status == CanonStatus.APPROVED
    ]
    set_id = st.text_input("Set ID", "likkle-jay-style-reference-set-v1")
    chosen = st.multiselect("Members (prefer 3–8 approved STYLE_REFERENCE)", approved_ids)
    set_notes = st.text_input("Set notes", "Curated Likkle Jay established style references")
    if st.button("CREATE / UPDATE REFERENCE SET") and chosen:
        try:
            s = vstore.create_or_update_set(set_id, chosen, notes=set_notes)
            st.success(f"Set {s.set_id} · {len(s.reference_ids)} refs · {_status_badge(s.status)}")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    for s in vstore.list_sets():
        with st.expander(f"{s.set_id} · {_status_badge(s.status)} · {len(s.reference_ids)} refs"):
            st.write(s.reference_ids)
            st.write(s.notes)
            if s.status != CanonStatus.APPROVED and st.button(
                "APPROVE REFERENCE SET", key=f"aset_{s.set_id}"
            ):
                try:
                    vstore.approve_set(s.set_id)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    st.markdown("### Canonical production registry (legacy list)")
    store = ReferenceStore(series_id, root=root)
    for a in store.list_assets():
        st.write(f"`{a.asset_id}` — {_status_badge(a.status)} — path={a.effective_path}")

elif nav == "Golden Frames":
    st.subheader("Golden references")
    gstore = GoldenFrameStore(series_id, root=root)
    gstore.ensure_s01e02_open_jar_placeholder()
    for g in gstore.list_all():
        with st.expander(f"{g.golden_id} · {_status_badge(g.status)}"):
            st.write(g.notes)
            if g.reference_required_reason:
                st.warning(g.reference_required_reason)
            if g.file and Path(g.file).is_file():
                st.image(g.file)
            upload = st.file_uploader(
                "Upload golden reference image",
                type=["png", "jpg", "webp"],
                key=f"gup_{g.golden_id}",
            )
            if upload is not None:
                dest = (
                    series_dir(series_id, root=root)
                    / "golden"
                    / "imports"
                    / g.golden_id
                    / upload.name
                )
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(upload.getvalue())
                gstore.attach_and_candidate(g.golden_id, dest)
                st.success("Attached as CANDIDATE")
                st.rerun()
            if st.button("LOCK AS GOLDEN REFERENCE", key=f"glock_{g.golden_id}"):
                try:
                    gstore.lock_as_golden(g.golden_id)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

elif nav == "Frames / Continuity":
    cont = series_dir(series_id, root=root) / "episodes" / "s01e02" / "continuity.json"
    if cont.is_file():
        st.json(json.loads(cont.read_text()))
    else:
        st.warning("No continuity.json yet.")

elif nav == "QA":
    st.write("QA outcomes: NOT_CHECKED | CHECKED | PASS | FAIL | REQUIRES_HUMAN_REVIEW")
    st.write(
        "Visual similarity uses perceptual hash heuristics → REVIEW_REQUIRED, never fake identity PASS."
    )
    st.code(f"Watermark must be exactly: {WATERMARK_EXACT}")
    st.code("Cookie jar label must be exactly: COOKIES")

elif nav == "Providers":
    st.subheader("Image providers + capability matrix")
    from capos.generation.provider_status import comfyui_dashboard_panel
    from capos.generation.smoke import run_provider_smoke_test
    from capos.hardware.profile import (
        detect_gpu,
        load_hardware_profile,
        resolve_generation_settings,
    )

    panel = comfyui_dashboard_panel()
    st.markdown("### COMFYUI LOCAL")
    g1, g2, g3, g4 = st.columns(4)
    g1.metric("Status", panel.get("status"))
    g2.metric("VRAM class", panel.get("vram_class"))
    g3.metric("Profile", panel.get("generation_profile"))
    g4.metric("Resolution", panel.get("resolution"))
    st.json(
        {
            "gpu": panel.get("gpu"),
            "model": panel.get("model"),
            "model_licence": panel.get("model_licence"),
            "workflow": panel.get("workflow"),
            "workflow_configured": panel.get("workflow_configured"),
            "workflow_reason": panel.get("workflow_reason"),
            "capabilities": panel.get("capabilities"),
            "concurrency": panel.get("concurrency"),
            "local_provider": panel.get("local_provider"),
            "production_eligible": panel.get("production_eligible"),
            "reason": panel.get("reason"),
        }
    )
    b1, b2 = st.columns(2)
    if b1.button("TEST CONNECTION"):
        from capos.generation.comfyui_backend import ComfyUIBackend

        st.write(ComfyUIBackend().available())
        st.json(comfyui_dashboard_panel())
    if b2.button("RUN SMOKE TEST"):
        with st.spinner("Running PROVIDER_SMOKE_TEST (non-canon)…"):
            st.json(run_provider_smoke_test(root=root))
    st.caption(
        "Smoke test is PROVIDER_SMOKE_TEST only — never auto-approved as style canon. "
        "Secrets are not displayed."
    )
    st.divider()
    st.write("Full capability matrix:")
    st.json(capability_matrix())
    st.write("Selected production provider:")
    st.json(select_production_provider())
    st.write("Hardware profile:")
    st.json(
        {
            "detected_gpu": detect_gpu(),
            "profile": load_hardware_profile().model_dump(mode="json"),
            "settings": resolve_generation_settings(),
        }
    )
    st.caption(
        "Prefer reference-based edit over full regeneration when supported. "
        "Mock is never production-eligible. LOW_VRAM_6GB concurrency=1."
    )

elif nav == "Readiness Gate":
    st.subheader("SEASON_PRODUCTION_READY")
    report = evaluate_season_production_ready(series_id, root=root)
    st.metric("Gate", "PASS" if report.season_production_ready else "FAIL")
    st.json(report.model_dump(mode="json"))

elif nav == "Animation":
    st.write("Simple animation plan support. No render claimed unless an output file exists.")

elif nav == "Audio":
    st.write("Provider-neutral voice / music / SFX. Subtitles from approved script — never OCR.")

elif nav == "Exports":
    st.write("FFmpeg slideshow with reframe metadata. Blocked when QA unresolved.")
    ok, detail = ffmpeg_available()
    st.write(f"ffmpeg available: {ok} ({detail})")

st.sidebar.divider()
st.sidebar.caption(f"Root: {root}")
st.sidebar.caption(
    f"Sample status: {StageStatus.DRAFT.value} / {CanonStatus.REFERENCE_REQUIRED.value}"
)
