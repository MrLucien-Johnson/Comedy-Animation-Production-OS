"""CAPOS Production UI — Streamlit dashboard."""

from __future__ import annotations

import json

import streamlit as st

from capos import __version__
from capos.core.paths import project_root, series_dir
from capos.core.schemas import WATERMARK_EXACT
from capos.core.status import StageStatus
from capos.domain.series import (
    list_series,
    load_episode_brief,
    load_script,
    load_series,
    load_storyboard,
)
from capos.export.ffmpeg_export import ffmpeg_available
from capos.generation.registry import health_all, try_register_optional_backends
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
        "Episodes",
        "Script",
        "Storyboard",
        "References",
        "Characters",
        "Locations",
        "Props",
        "Frames / Continuity",
        "QA",
        "Animation",
        "Audio",
        "Exports",
    ],
)

series_ids = list_series(root=root)
series_id = st.sidebar.selectbox("Series", series_ids or ["likkle-jay"])

if nav == "Dashboard":
    st.subheader("Production dashboard")
    cols = st.columns(4)
    ff_ok, ff = ffmpeg_available()
    cols[0].metric("Series", len(series_ids))
    cols[1].metric("FFmpeg", "yes" if ff_ok else "no")
    cols[2].metric("Engineering", "partial")
    cols[3].metric("Content prod", "not claimed")
    st.write("Backend health (honest availability):")
    st.json(health_all())
    gates_path = root / "config" / "production_gates.json"
    if gates_path.is_file():
        st.write("Production gates:")
        st.json(json.loads(gates_path.read_text()))
    st.info(
        "Statuses to watch: what exists, what is approved, what failed, "
        "what is missing, what needs regeneration."
    )

elif nav == "Series":
    st.subheader("Series")
    if (series_dir(series_id, root=root) / "series.json").is_file():
        st.json(load_series(series_id, root=root).model_dump())
        bible = series_dir(series_id, root=root) / "BIBLE.md"
        if bible.is_file():
            st.markdown(bible.read_text())

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
    script = load_script(series_id, ep, root=root)
    st.json(script.model_dump())

elif nav == "Storyboard":
    ep = st.selectbox("Episode", ["s01e01", "s01e02", "s01e03"], key="sb")
    beats = load_storyboard(series_id, ep, root=root)
    st.json([b.model_dump() for b in beats])

elif nav == "References":
    store = ReferenceStore(series_id, root=root)
    assets = store.list_assets()
    st.write(f"{len(assets)} canonical assets")
    for a in assets:
        st.write(f"`{a.asset_id}` — {a.status} — path={a.path}")

elif nav in {"Characters", "Locations", "Props"}:
    kind = nav.lower()
    base = series_dir(series_id, root=root) / kind
    if base.is_dir():
        for p in sorted(base.iterdir()):
            if p.is_dir():
                st.markdown(f"### {p.name}")
                for f in p.glob("*.json"):
                    st.json(json.loads(f.read_text()))

elif nav == "Frames / Continuity":
    cont = series_dir(series_id, root=root) / "episodes" / "s01e02" / "continuity.json"
    if cont.is_file():
        st.json(json.loads(cont.read_text()))
    else:
        st.warning("No continuity.json yet — run continuity build / compile-e2 workflow.")

elif nav == "QA":
    st.write("QA outcomes: NOT_CHECKED | CHECKED | PASS | FAIL | REQUIRES_HUMAN_REVIEW")
    st.write("Export is fail-closed unless all required QA = PASS or explicit human override.")
    st.code(f"Watermark must be exactly: {WATERMARK_EXACT}")
    st.code("Cookie jar label must be exactly: COOKIES")

elif nav == "Animation":
    st.write("Simple animation plan support: pans, zoom, parallax, blink, mouth, arm, prop motion.")
    st.caption("No animation is claimed rendered unless an output file exists.")

elif nav == "Audio":
    st.write("Provider-neutral voice / music / SFX interfaces. Null backend reports unavailable.")
    st.write("Subtitles: SRT/VTT from approved script — never OCR.")

elif nav == "Exports":
    st.write("FFmpeg slideshow assembly with reframe metadata (1:1, 9:16, 16:9, 4:5).")
    st.write("Blocked when QA unresolved unless human override.")
    ok, detail = ffmpeg_available()
    st.write(f"ffmpeg available: {ok} ({detail})")

st.sidebar.divider()
st.sidebar.caption(f"Root: {root}")
st.sidebar.caption(f"Default series status sample: {StageStatus.DRAFT.value}")
