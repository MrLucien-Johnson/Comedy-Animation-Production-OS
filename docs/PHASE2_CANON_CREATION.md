# Phase 2 — Canon Creation & Approval

## Baseline (before Phase 2)

- pytest: 34 passed
- ruff: clean
- providers: mock AVAILABLE; huggingface/local NOT_CONFIGURED; null UNAVAILABLE
- `HF_TOKEN`: unset
- SEASON_PRODUCTION_READY: FAIL

## Delivered engineering

- Production storage tree under `production/likkle-jay/`
- Provider capability matrix (`TEXT_TO_IMAGE`, `IMAGE_TO_IMAGE`, `REFERENCE_IMAGE`, …)
- Production provider selection **excludes mock**
- Canon creation pipeline with dependency order
- Candidate batches + `AWAITING_HUMAN_SELECTION` / `BLOCKED_NO_PROVIDER`
- Human selection cannot lock mock/non-production art
- COMPARE TO CANON diff helper
- Deterministic `COOKIES` prop-label compositor
- ComfyUI backend stub (`CAPOS_COMFYUI_URL`)
- Streamlit: Canon Candidates + Compare to Canon
- Phase 2 tests

## Actual images generated

**0 production images** — no production-eligible provider configured.

Style/character/location/prop candidate generation correctly returns
`BLOCKED_NO_PROVIDER` rather than writing mock art into the canon path.

## Human actions required

1. Configure a real provider (`HF_TOKEN`, local Diffusers, or ComfyUI)
2. Run `scripts/phase2_generate_style_candidates.py`
3. Select style candidate in UI → APPROVE → LOCK
4. Continue dependency chain (Jay → Bev → turnarounds → locations → props → golden)

## Gates

| Gate | Status |
|------|--------|
| ENGINEERING COMPLETE | YES (Phase 2 systems) |
| CONTENT PRODUCTION READY | NO / PARTIAL (workflows ready; no approved images) |
| SEASON PRODUCTION READY | FAIL |
