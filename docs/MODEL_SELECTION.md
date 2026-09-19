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

## Initial production choice (operator-verified)

| Field | Value |
|-------|-------|
| Checkpoint | `toonyou_beta6.safetensors` |
| Source | `frankjoshua/toonyou_beta6` (+ Civitai ToonYou listing) |
| Architecture | SD1.5-class |
| VRAM class | LOW_6GB — RECOMMENDED |
| Provenance file | `config/model_provenance/toonyou_beta6.json` |
| Licence status | **UNVERIFIED** until human confirms source terms |
| Commercial use | **REQUIRES_AUTHOR_CONTACT** per published author addendum (not “FREE”) |

Do **not** label ToonYou as unrestricted commercial. Set:

```bash
CAPOS_COMFYUI_CHECKPOINT=toonyou_beta6.safetensors
CAPOS_COMFYUI_MODEL_LICENCE="reviewed notes…"
CAPOS_COMFYUI_MODEL_LICENCE_STATUS=VERIFIED   # only after review
```

and update `commercial_use_operator_ack` in the provenance JSON when commercial permission is resolved.

`SEASON_PRODUCTION_READY` **fails closed** while licence is unverified / commercial ack missing.

### Phase 2B — model is not sacred

ToonYou proved **provider/infrastructure** success on RTX 3050. That does **not** lock it as the artistic production checkpoint.

If reference-conditioned ToonYou cannot recover the established Likkle Jay visual language:

1. Mark `MODEL_STYLE_MISMATCH`
2. Evaluate another **SD1.5-compatible** low-VRAM cartoon checkpoint
3. Keep `PROVIDER=ComfyUI` with replaceable `CAPOS_COMFYUI_CHECKPOINT`

Do **not** move to FLUX/large models or raise resolution to “fix” style drift. See `docs/PHASE2B_STYLE_RECOVERY.md`.

## Capability needs for Likkle Jay