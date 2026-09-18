# Engineering vs Content Readiness

## Three gates (keep separate)

| Gate | Meaning | Current |
|------|---------|---------|
| **ENGINEERING COMPLETE** | Code, schemas, workflows, tests | **YES** (Phase 2) |
| **CONTENT PRODUCTION READY** | Approved canonical **images** exist | **NO** (workflows ready; 0 approved images) |
| **SEASON PRODUCTION READY** | Minimum canon APPROVED + real provider + golden refs | **NO** (fail-closed) |

## Engineering readiness

| Area | Status |
|------|--------|
| Phase 0–1 foundation | Ready |
| Production storage hierarchy | Ready |
| Provider capability matrix | Ready |
| Canon creation pipeline (dependency order) | Ready |
| Candidate batches + human selection | Ready |
| COMPARE TO CANON | Ready |
| COOKIES / watermark compositors | Ready |
| ComfyUI / HF / local provider stubs | Ready (config-gated) |
| Tests | Phase 2 suite included |

## Content-production readiness

| Area | Status |
|------|--------|
| Approved style master image | **Not ready** |
| Approved character masters | **Not ready** |
| Turnarounds / expressions on disk | **Not ready** |
| Location / prop masters on disk | **Not ready** |
| S01E02 F3 golden | **REFERENCE_REQUIRED** |
| Real provider | **NOT_CONFIGURED** (mock only — not production-eligible) |

## Exact blocker for visual generation

No production-eligible image provider is configured:

- `HF_TOKEN` unset → Hugging Face `NOT_CONFIGURED`
- Local Diffusers not installed/configured
- `CAPOS_COMFYUI_URL` unset

**Mock art is intentionally refused as production canon.**

## Next human actions

1. Set a real provider credential/config in `.env` (never commit secrets)
2. `python scripts/phase2_generate_style_candidates.py`
3. Select + APPROVE + LOCK style in Streamlit
4. Continue the dependency chain
