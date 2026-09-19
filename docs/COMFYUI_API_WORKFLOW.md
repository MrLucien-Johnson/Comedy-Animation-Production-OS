# ComfyUI API Workflow Import — CAPOS

## Preferred placement

```text
workflows/comfyui/style-master-toonyou-beta6.json   # CAPOS-ready (matches operator-verified topology)
workflows/comfyui/style-master-low-vram.json         # generic template (template_only until configured)
```

Or point env at an absolute export (never commit machine-specific paths in git):

```bash
CAPOS_COMFYUI_WORKFLOW_PATH=/absolute/path/to/your_export_api.json
```

## How to export from ComfyUI Desktop

1. Open the verified graph (checkpoint → CLIP± → Empty Latent → KSampler → VAE Decode → Save Image)
2. Use ComfyUI’s **Save (API Format)** / API export (wording varies by Desktop build — use the menu that exports the prompt dict for `/prompt`, not the UI-layout workflow)
3. Save/replace under `workflows/comfyui/` **or** set `CAPOS_COMFYUI_WORKFLOW_PATH`
4. Ensure checkpoint filename matches `CAPOS_COMFYUI_CHECKPOINT=toonyou_beta6.safetensors`

## CAPOS injection

CAPOS injects (and records) explicitly:

| Field | Source |
|-------|--------|
| checkpoint | `CAPOS_COMFYUI_CHECKPOINT` |
| positive / negative | prompt compiler |
| seed | permanent candidate seed map — **never** uncontrolled randomize |
| width / height | hardware SAFE profile (512×512) |
| steps / cfg / sampler / scheduler / denoise | SAFE defaults 20 / 7.0 / euler / normal / 1.0 |

Validation: `capos.generation.comfyui.validate.validate_api_workflow`.

## Local activate

```bash
python scripts/phase2a_local_activate.py          # connect + validate
python scripts/phase2a_local_activate.py --smoke  # PROVIDER_SMOKE_TEST
python scripts/phase2a_local_activate.py --smoke --style  # then exactly 3 style candidates
```

Cloud agents without your GPU will report `LOCAL_EXECUTION_REQUIRED`.
