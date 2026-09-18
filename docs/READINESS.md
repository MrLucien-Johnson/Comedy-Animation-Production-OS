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
LOCAL_PROVIDER = SETUP_REQUIRED
```

Cloud/agent environments without NVIDIA + ComfyUI cannot generate production images.
The production machine (RTX 3050 6 GB) must complete setup below.

**Mock art is intentionally refused as production canon.**

## Exact blocker for visual generation

1. `CAPOS_COMFYUI_URL` unset or ComfyUI unreachable  
2. Checkpoint / workflow still `template_only` or `CAPOS_COMFYUI_CHECKPOINT` unset  
3. Model licence not recorded (`CAPOS_COMFYUI_MODEL_LICENCE`)

## Exact human / machine actions (production GPU)

1. Follow `docs/COMFYUI_LOCAL_SETUP.md` (RTX 3050 6 GB section)  
2. Follow `docs/MODEL_SELECTION.md` — pick one SD1.5-class cartoon checkpoint; record licence  
3. Set env (never commit secrets):

```bash
CAPOS_COMFYUI_URL=http://127.0.0.1:8188
CAPOS_COMFYUI_CHECKPOINT=your_model.safetensors
CAPOS_COMFYUI_MODEL_LICENCE="licence-id-or-URL"
# clear template_only or:
# CAPOS_COMFYUI_WORKFLOW_PATH=/path/to/exported_api_workflow.json
```

4. `python scripts/phase2a_comfyui_smoke_and_style.py`  
5. Open Streamlit → **Canon Candidates** → select ONE style → APPROVE/LOCK  
6. Stop — do not auto-advance to characters until style is human-approved  

## Docs

- `docs/COMFYUI_LOCAL_SETUP.md`  
- `docs/MODEL_SELECTION.md`  
- `docs/IMAGE_GENERATION.md`  
- `docs/PHASE2_CANON_CREATION.md`  
