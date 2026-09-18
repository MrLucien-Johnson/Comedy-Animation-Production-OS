# Phase 1 — Real Production Activation

## Goal

Move from engineering foundation → canonical visual production pipeline
**without** mass episode generation.

## Sequence

```
CANON registry → REVIEW → APPROVE (with files) → GOLDEN REFERENCES → PRODUCTION
```

## Additions

- Canonical asset types (`CHARACTER_MASTER`, turnarounds, expressions, locations, props, style, …)
- `CanonStatus`: DRAFT → CANDIDATE → REVIEW_REQUIRED → APPROVED / REJECTED / SUPERSEDED / REFERENCE_REQUIRED
- Relative scale manifest (`series/*/scale/relative_scale.json`)
- Spatial location spaces (`series/*/spatial/*.json`)
- Golden frame store + S01E02 F3 REFERENCE_REQUIRED placeholder
- Provider availability: AVAILABLE / NOT_CONFIGURED / UNAVAILABLE / DEGRADED
- Text masters: SPEECH_BUBBLE, PROP_LABEL, WATERMARK, COVER_TITLE
- Visual QA perceptual hash (never claims identity PASS)
- `SEASON_PRODUCTION_READY` fail-closed validator
- Dashboard: Canon, Golden Frames, Providers, Readiness Gate

## Honesty

Bootstrap creates **registry metadata only**.  
`images_created: 0`. No approved production images are claimed.
