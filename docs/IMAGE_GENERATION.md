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
| `huggingface` | Requires `HF_TOKEN` + `huggingface_hub` |
| `local` | Requires torch/diffusers + configured weights |
| `comfyui` | Requires `CAPOS_COMFYUI_URL` (+ workflow path for generate) |
| `null` | Always unavailable (tests) |

## Capability matrix

Providers report: `TEXT_TO_IMAGE`, `IMAGE_TO_IMAGE`, `REFERENCE_IMAGE`, `INPAINT`, `OUTPAINT`, `CONTROL_IMAGE`, `SEED`, `NEGATIVE_PROMPT`.

`select_production_provider()` never returns mock.

## Prefer reference edits

When only an arm/pose changes: keep background, hair, face, clothes, props, camera; change the pose via edit/inpaint when the provider supports it.

## Safety

Prompts describe fictional animated family-friendly cartoons. Provider refusals are recorded; prompts may be revised without changing story intent. Never weaken platform safety controls.
