# Image Generation

## Provider abstraction

```text
generate_image / generateImage
edit_image / editImage
generate_variation / generateVariation
reference_image / referenceImage
inpaint
outpaint
```

Backends register in `capos.generation.registry`. Availability is probed — never fabricate success.

| Backend | Notes |
|---------|-------|
| `mock` | Always available; **non-production** — cannot lock as canon |
| `huggingface` | Requires `HF_TOKEN` + `huggingface_hub` (not primary route) |
| `local` | Requires torch/diffusers + configured weights |
| `comfyui` | **Preferred production route** — `CAPOS_COMFYUI_URL` + local checkpoint/workflow |
| `null` | Always unavailable (tests) |

## Primary production route (Phase 2A)

```text
CAPOS → ComfyUI local API → VRAM-aware workflow → RTX 3050 6GB
  → candidate → QA → human approval → canonical asset
```

Hardware profile: `LOW_VRAM_6GB` (`config/hardware.json`).

- Generation concurrency **1**  
- Default diffusion **512×512** (SAFE profile)  
- Output/export resolution is separate — optional upscale after human selection  
- CUDA OOM → bounded retry with smaller sizes → `FAILED_RESOURCE_LIMIT`  
- Never silently fall back to mock  

See `docs/COMFYUI_LOCAL_SETUP.md` and `docs/MODEL_SELECTION.md`.

## Capability matrix

Providers report: `TEXT_TO_IMAGE`, `IMAGE_TO_IMAGE`, `REFERENCE_IMAGE`, `INPAINT`, `OUTPAINT`, `CONTROL_IMAGE`, `SEED`, `NEGATIVE_PROMPT`.

`select_production_provider()` prefers `comfyui`, never returns mock.

## Prefer reference edits

When only an arm/pose changes: keep background, hair, face, clothes, props, camera; change the pose via edit/inpaint when the provider supports it.

On 6 GB VRAM, stage reference conditioning — do not stack large checkpoint + multiple ControlNets + high res + upscale in one graph.

## Deterministic graphics

Keep out of diffusion where possible: watermark `MRLUCIENJOHNSON`, `COOKIES` label, speech bubbles, dialogue, titles, subtitles. Composite after artwork.

## Safety

Prompts describe fictional animated family-friendly cartoons. Provider refusals are recorded; prompts may be revised without changing story intent. Never weaken platform safety controls.
