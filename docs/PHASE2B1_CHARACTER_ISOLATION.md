# Phase 2B.1 — Character Isolation

## Context

Phase 2B produced **3 real ComfyUI IMG2IMG** candidates — technical success.

They are **NOT approved** as style canon:

`TECHNICAL_SUCCESS_STYLE_RECOVERY_NOT_YET_APPROVED`

Reason: candidates mutated the entire **character sheet** (layout, typography, multi-views).

Next milestone: **three clean standalone Likkle Jay images**, not another sheet.

## Strategy (zero-cost local, ordered)

| Priority | Method | Status |
|----------|--------|--------|
| 1 | Cropped character reference + controlled img2img | **ACTIVE (2B.1)** |
| 2 | IP-Adapter (SD1.5) if VRAM allows | Documented — not auto-installed |
| 3 | ControlNet / OpenPose for pose | Later |
| 4 | LoRA training | Future explicit approval only |

### IP-Adapter (optional later)

If cropped img2img still cannot hold identity without sheet contamination, evaluate:

- ComfyUI IP-Adapter Plus (SD1.5)
- `ip-adapter_sd15.safetensors` (or light variant)
- CLIP vision encoder required by the node pack

**Do not download automatically.** On 6GB: run IP-Adapter alone with 512², batch 1 — never stack with ControlNet + heavy adapters in one graph.

Report required files/nodes in a future PR before installing.

## Visual crop UI

Streamlit uses **`streamlit-cropper`** (free) so the operator drags a rectangle on
the displayed sheet. Coordinates are mapped back to **ORIGINAL file pixels**.

### Cause of the previous numeric-crop failure

`st.image` showed a browser-scaled preview of the 1254×1254 sheet, while
`number_input` values were applied as original-file pixels via `PIL.crop`.
Defaults `right≤256` / `bottom≤512` selected the upper-left logo. This was
**display vs original scale confusion** — not 512×512 normalization or EXIF.

Install on the RTX 3050 machine if needed:

```powershell
pip install "streamlit-cropper>=0.3.1,<0.4"
```


## Denoise experiment (hard band 0.30–0.45)

| Slot | Seed | Denoise |
|------|------|---------|
| A | 415011 | 0.30 |
| B | 415022 | 0.375 |
| C | 415033 | 0.45 |

`0.50` is **not** used — blocked by Phase 2B denoise policy band.

## Commands

```powershell
# Mark 2B recovery hold
python scripts/phase2b1_character_isolation.py --hold-only

# Create derived crop (adjust pixel box to front Jay on your sheet)
python scripts/phase2b1_character_isolation.py --crop LEFT TOP RIGHT BOTTOM --approve-derived

# Or use Streamlit → References → CREATE DERIVED CHARACTER REFERENCE

# Generate 3 isolation candidates
python scripts/phase2b1_character_isolation.py --generate
```

## Gate

`AWAITING_HUMAN_CHARACTER_ISOLATION_REVIEW`

Do not: approve style, generate Auntie Bev, scenes, episodes, alter canon, train LoRA.
