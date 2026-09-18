# Phase 2A — Local ComfyUI Activation (LOW_VRAM_6GB)

## Hardware constraint

Production target: **NVIDIA GeForce RTX 3050 · ~6 GB VRAM**.

Profile: `LOW_VRAM_6GB` / SAFE · concurrency **1** · diffusion **512×512**.

## Delivered engineering

- ComfyUI HTTP client (health, queue, history, view, interrupt, OOM classification)
- `ComfyUIBackend` with bounded OOM retries + resolution fallback
- Hardware profile + SAFE/BALANCED/QUALITY generation profiles
- Generation concurrency lock (serial jobs only)
- Workflow templates under `workflows/comfyui/` (`template_only` until local configure)
- Telemetry + upscaled derivative provenance
- Providers UI: TEST CONNECTION / RUN SMOKE TEST
- Canon Candidates: preview + model/seed/resolution/duration + SELECT/REJECT
- `scripts/phase2a_comfyui_smoke_and_style.py`
- Docs: `COMFYUI_LOCAL_SETUP.md`, `MODEL_SELECTION.md`

## Stop outcomes

| Outcome | Meaning |
|---------|---------|
| **A** | `LOCAL_PROVIDER = SETUP_REQUIRED` — engineering done; install ComfyUI + model on GPU machine |
| **B** | Smoke OK + exactly 3 style candidates → `AWAITING_HUMAN_STYLE_SELECTION` |

## Non-negotiables

No mock art as canon. No automatic style approval. No parallel diffusion. No mass Season 1 generation.
