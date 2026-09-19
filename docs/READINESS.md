# Engineering vs Content Readiness

## Three gates (keep separate)

| Gate | Meaning | Current |
|------|---------|---------|
| **ENGINEERING COMPLETE** | Code, schemas, workflows, tests | **YES** (Phase 2A engineering) |
| **CONTENT PRODUCTION READY** | Approved canonical **images** exist | **NO** (0 approved images) |
| **SEASON PRODUCTION READY** | Minimum canon APPROVED + real provider + golden refs | **NO** (fail-closed) |

## Engineering readiness

| Area | Status |
|------|--------|
| Phase 0–2 foundation | Ready |
| Phase 2A ComfyUI client / OOM / telemetry | Ready |
| `LOW_VRAM_6GB` hardware profile (RTX 3050 class) | Ready — concurrency **1**, SAFE **512×512** |
| Workflow templates (`workflows/comfyui/`) | On disk as `template_only` until local checkpoint configured |
| Production storage hierarchy | Ready |
| Provider capability matrix | Ready (ComfyUI preferred) |
| Canon creation pipeline (dependency order) | Ready — sequential generation |
| Candidate batches + human selection | Ready |
| Upscale derivative provenance | Ready (optional, post-selection) |
| Tests | Phase 2A suite included |

## Content-production readiness

| Area | Status |
|------|--------|
| Approved style master image | **Not ready** |
| Approved character masters | **Not ready** |
| Turnarounds / expressions on disk | **Not ready** |
| Location / prop masters on disk | **Not ready** |
| S01E02 F3 golden | **REFERENCE_REQUIRED** |
| Real local provider | **SETUP_REQUIRED** until ComfyUI + model on production GPU |

## Local provider status

```text
ENGINEERING_ENVIRONMENT: NO LOCAL GPU / COMFYUI ACCESS (typical cloud agent)
PRODUCTION_MACHINE: LOCAL COMFYUI MANUALLY VERIFIED BY OPERATOR
  checkpoint=toonyou_beta6.safetensors @ 512×512 SAFE (euler/normal/20/cfg7)

On this cloud workspace: LOCAL_EXECUTION_REQUIRED
On production machine after activate: LOCAL_RUNTIME_VERIFIED → AWAITING_HUMAN_STYLE_SELECTION
```

**Mock art is intentionally refused as production canon.**

## Exact blocker for visual generation (cloud)

Cloud cannot reach the operator’s `127.0.0.1:8188`. Run activation on the RTX 3050 machine.

## Exact human actions (production GPU)

1. Start ComfyUI Desktop API  
2. Copy `.env.example` → `.env` (never commit) with checkpoint + URL  
3. Optional: export API workflow — see `docs/COMFYUI_API_WORKFLOW.md`  
4. Review licence in `config/models/toonyou_beta6.json` (do not assume commercial “free”)  
5. `python scripts/phase2a_local_activate.py --smoke --style`  
6. Streamlit → Canon Candidates → SELECT style → stop until human approval  

## Docs

- `docs/COMFYUI_LOCAL_SETUP.md`  
- `docs/COMFYUI_API_WORKFLOW.md`  
- `docs/MODEL_SELECTION.md`  
- `docs/PHASE2A_COMFYUI_LOW_VRAM.md`  
