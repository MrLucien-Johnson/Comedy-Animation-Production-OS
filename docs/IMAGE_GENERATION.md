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
| `mock` | Always available; labeled non-production |
| `huggingface` | Requires `HF_TOKEN` + `huggingface_hub` |
| `null` | Always unavailable (for tests) |

## Prefer reference edits

When only an arm/pose changes: keep background, hair, face, clothes, props, camera; change the pose via edit/inpaint when the provider supports it.

## Safety

Prompts describe fictional animated family-friendly cartoons. Provider refusals are recorded; prompts may be revised without changing story intent. Never weaken platform safety controls.
