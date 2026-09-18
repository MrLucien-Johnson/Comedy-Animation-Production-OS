"""CAPOS Production UI — Streamlit dashboard with Canon workflow."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from capos import __version__
from capos.canon.bootstrap import bootstrap_likkle_jay_canon
from capos.canon.candidates import CandidateStore
from capos.canon.diff import compare_to_canon
from capos.canon.pipeline import CanonCreationPipeline
from capos.core.paths import project_root, series_dir
from capos.core.schemas import WATERMARK_EXACT
from capos.core.status import CanonStatus, StageStatus
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
    st.subheader("Canon candidate batches (human selection required)")
    pipe = CanonCreationPipeline(series_id, root=root)
    st.json(pipe.next_actionable_step())
    c1, c2, c3 = st.columns(3)
    if c1.button("Generate STYLE candidates (×3)"):
        batch = pipe.generate_style_candidates(count=3)
        st.write(batch.model_dump())
        st.rerun()
    if c2.button("Generate LIKKLE JAY candidates (×3)"):
        st.write(pipe.generate_likkle_jay_candidates(count=3).model_dump())
        st.rerun()
    if c3.button("Generate AUNTIE BEV candidates (×3)"):
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
    for batch in store_b.list_batches():
        with st.expander(
            f"{batch.batch_id} · {_status_badge(batch.status)} → {batch.target_asset_id}"
        ):
            if batch.blocker:
                st.error(batch.blocker)
            st.write(batch.recommendation_notes)
            for cand in batch.candidates:
                cols = st.columns([1, 2, 1])
                if cand.file and Path(cand.file).is_file():
                    cols[0].image(cand.file, use_container_width=True)
                else:
                    cols[0].warning("No file")
                cols[1].json(cand.model_dump())
                if cand.non_production:
                    cols[2].warning("NON-PRODUCTION — cannot lock as canon")
                elif cols[2].button("Select", key=f"sel_{batch.batch_id}_{cand.candidate_id}"):
                    try:
                        pipe.promote_selection_to_canon(batch.batch_id, cand.candidate_id)
                        st.success(
                            f"Selected {cand.candidate_id}. Now APPROVE on Canon page to lock."
                        )
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
    st.json(capability_matrix())
    st.write("Selected production provider:")
    st.json(select_production_provider())
    st.caption(
        "Prefer reference-based edit over full regeneration when supported. "
        "Mock is never production-eligible."
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
