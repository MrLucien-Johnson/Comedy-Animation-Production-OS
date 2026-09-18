# Model Selection — LOW_VRAM_6GB (RTX 3050 class)

## Priorities

1. Character consistency  
2. Reference control  
3. 2D cartoon quality  
4. Location consistency  
5. Low VRAM operation  
6. Reproducibility  
7. Generation speed  
8. Maximum raw resolution (secondary to reliability)

A smaller model with strong img2img/reference support beats a huge model that OOMs.

## Hardware class

`LOW_VRAM_6GB` (~6 GB). Default diffusion size **512×512**. Optional upscale after human selection.

## Classification rubric

| Class | Meaning |
|-------|---------|
| RECOMMENDED | Fits 6 GB reliably; good cartoon/reference path |
| SUPPORTED | Usable with SAFE profile / reduced settings |
| EXPERIMENTAL | May work; expect OOM risk |
| TOO_HEAVY | Frequently OOM / multi-stage only |
| INCOMPATIBLE | Wrong licence, architecture, or ComfyUI support |

## Practical candidate families (evaluate locally — do not download all)

| Family | Notes | Tentative class |
|--------|-------|-----------------|
| SD 1.5 checkpoints (cartoon fine-tunes) | Strong ecosystem; ControlNet/IP-Adapter options; often best fit for 6 GB | RECOMMENDED / SUPPORTED |
| SDXL base | Higher quality potential; tighter VRAM; start SAFE 512 only | EXPERIMENTAL / TOO_HEAVY on stacked adapters |
| Large “newest” DiT / huge FLUX variants | Often exceed 6 GB when loaded with extras | TOO_HEAVY for stacked production |
| Distilled / turbo variants | Faster; validate cartoon style + licence | SUPPORTED / EXPERIMENTAL |

**Do not hard-code a single model name in code until the local machine confirms load + smoke test.**

Set after local choice:

```bash
CAPOS_COMFYUI_CHECKPOINT=your_model.safetensors
CAPOS_COMFYUI_MODEL_LICENCE="license-id-or-URL"
```

## Licensing checklist (required before production canon)

Record for the chosen model:

- model name / version  
- source URL  
- licence text / SPDX if available  
- commercial-use implications  
- checksum when practical  

“Free download” ≠ unrestricted commercial use.

## Capability needs for Likkle Jay

Prefer workflows that can grow into:

- text-to-image (style/location empty masters)  
- image-to-image (turnarounds/expressions from approved master)  
- optional ControlNet / IP-Adapter **only if VRAM budget allows**  
- inpaint for localized edits  

Staged generation > stacking everything in one graph.

## Initial production choice process

1. Install ComfyUI on the RTX 3050 machine  
2. Load one SD1.5-class cartoon checkpoint under SAFE 512  
3. Run CAPOS smoke test workflow  
4. If stable, clear `template_only` on `style-master-low-vram.json` (or point `CAPOS_COMFYUI_WORKFLOW_PATH`)  
5. Generate three style candidates sequentially  
6. Human selects style  
7. Only then enable BALANCED/QUALITY after telemetry proves stability  
