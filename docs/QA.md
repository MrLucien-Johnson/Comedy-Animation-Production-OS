# QA

## Validators

`DIMENSION_CHECK`, `ASPECT_RATIO_CHECK`, `REFERENCE_CHECK`, `CHARACTER_CHECK`, `OUTFIT_CHECK`, `PROP_PRESENCE_CHECK`, `PROP_STATE_CHECK`, `BACKGROUND_CHECK`, `TEXT_CHECK`, `WATERMARK_CHECK`, `SEQUENCE_CHECK`, `FILE_CHECK`

## Visual similarity

Interfaces exist for reference / character / background / prop similarity.  
If no CV backend is configured, status is **`NOT_CHECKED`** — never pretend PASS.

## Outcomes

`NOT_CHECKED | CHECKED | PASS | FAIL | REQUIRES_HUMAN_REVIEW`

## Fail closed

QA failure → frame `QA_FAILED` → export blocked unless explicit human override.

## Deterministic exactness tests

- Watermark must be exactly `MRLUCIENJOHNSON`  
- Cookie label must be exactly `COOKIES` (not `COOKIE`)  
- Locked dialogue must match byte-for-byte when composited  
