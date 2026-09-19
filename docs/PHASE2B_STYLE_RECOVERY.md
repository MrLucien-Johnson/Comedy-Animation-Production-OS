# Phase 2B — Reference-Grounded Style Recovery

## Verdict from Phase 2A

Phase 2A proved the **local ComfyUI → RTX 3050 6 GB → ToonYou** pipeline works.

All three text-only style masters are **HUMAN_REJECTED_STYLE_DRIFT**:

| Candidate | Status |
|-----------|--------|
| style-master-candidate-001 | REJECTED (preserve files + provenance) |
| style-master-candidate-002 | REJECTED |
| style-master-candidate-003 | REJECTED |

**Reason:** `NOT_CLOSE_ENOUGH_TO_ESTABLISHED_LIKKLE_JAY_STYLE`  
Anime/adventure lean, elongated proportions, angular faces, cinematic detail.

They must **never** be selected as canon.

## Strategy: STYLE RECOVERY (not invention)

```
APPROVED EXISTING LIKKLE JAY ART
        ↓
REFERENCE INGESTION
        ↓
STYLE REFERENCE MASTER SET
        ↓
REFERENCE-CONDITIONED GENERATION (img2img)
        ↓
3 STYLE RECOVERY CANDIDATES
        ↓
HUMAN REVIEW (Compare to Reference)
        ↓
STYLE CANON APPROVAL
        ↓
(only then) LIKKLE JAY CHARACTER MASTER
```

## Reference ingestion

UI: **References → Import Visual Reference**

Supported: PNG / JPG / WEBP

Store: `series/likkle-jay/visual_references/`

| Field | Notes |
|-------|-------|
| reference ID | Unique; never overwritten |
| type | STYLE / CHARACTER / LOCATION / PROP / GOLDEN_FRAME |
| checksum | SHA-256 |
| status | CANDIDATE → APPROVE |
| provenance | original filename + import metadata |

Preferred set: **`likkle-jay-style-reference-set-v1`** (3–8 curated images).

Import folder (exact):

```
series/likkle-jay/visual_references/imports/
```

## Conditioning study (RTX 3050 / 6 GB)

| Method | VRAM risk | Phase 2B choice |
|--------|-----------|-----------------|
| **IMAGE-TO-IMAGE** (VAE encode + denoise) | Lowest | **FIRST / preferred** |
| IP-Adapter | Higher | Later if img2img insufficient |
| ControlNet | Higher | Only if needed for pose/line |
| Full stack simultaneous | OOM risk | **Do not** |

Provider = ComfyUI; **checkpoint is replaceable**. ToonYou proved infrastructure, not artistic lock. If recovery still drifts, mark `MODEL_STYLE_MISMATCH` and evaluate another SD1.5 cartoon checkpoint — do **not** jump to FLUX/large models.

## Img2img workflow

`workflows/comfyui/style-recovery-img2img-low-vram.json`

```
REFERENCE → LoadImage → VAEEncode → KSampler(denoise) → Decode → Save
```

Denoise production parameters (conservative band):

| Candidate | Seed | Denoise |
|-----------|------|---------|
| style-recovery-candidate-001 | 405011 | 0.35 |
| style-recovery-candidate-002 | 405022 | 0.45 |
| style-recovery-candidate-003 | 405033 | 0.55 |

512×512 · batch 1 · concurrency 1 · sequential.

Validation must **generalise** style (new pose/composition), not copy the reference frame.

## Scripts

```bash
# Mark Phase 2A rejected + report stop state
python scripts/phase2b_reject_style_drift.py

# After references approved — generate exactly 3 recovery candidates
python scripts/phase2b_style_recovery_generate.py
```

## Stop states

| State | Meaning |
|-------|---------|
| `AWAITING_STYLE_REFERENCE_IMPORT` | No approved style reference set yet |
| `AWAITING_HUMAN_STYLE_RECOVERY_REVIEW` | 3 recovery candidates ready for human |
| Character production | **BLOCKED** until style approved |

## Human review categories (Compare to Reference)

LINEWORK_MATCH · SHAPE_LANGUAGE_MATCH · COLOUR_LANGUAGE_MATCH · SHADING_MATCH ·  
FACE_STYLE_MATCH · BACKGROUND_STYLE_MATCH · COMEDY_EXPRESSIVENESS ·  
ANIME_DRIFT · PHOTOREALISM_DRIFT · OVER_DETAILING · OVERALL_CONTINUITY

No fake semantic identity score. Human review remains authoritative.

## Text policy

Diffusion must not render: MRLUCIENJOHNSON, COOKIES, speech bubbles, dialogue, titles.  
Continue deterministic compositing.
