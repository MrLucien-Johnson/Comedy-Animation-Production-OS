# ComfyUI Local Setup — CAPOS

Primary production route for Likkle Jay on local NVIDIA GPUs.

## RTX 3050 6 GB SETUP

This project defaults to hardware profile `LOW_VRAM_6GB`:

- concurrency **1**
- default diffusion **512×512**
- OOM bounded retries with smaller sizes
- optional upscale **after** human selection

### Install ComfyUI (on the production machine)

Follow upstream ComfyUI documentation for the current version. Typical outline:

1. Install recent NVIDIA drivers + CUDA-compatible PyTorch for your OS  
2. Clone ComfyUI into a local directory  
3. Create a venv and install ComfyUI requirements  
4. Place checkpoints under ComfyUI `models/checkpoints/`  
5. Start the server and confirm `http://127.0.0.1:8188` loads  

**Do not invent CLI flags.** On the machine where ComfyUI is installed, run the app’s own help, for example:

```bash
python main.py --help
```

Use only flags that appear there. Many builds document low-VRAM related options; prefer those that match your installed version rather than blog posts for older forks.

### CAPOS configuration

```bash
# .env (never commit)
CAPOS_COMFYUI_URL=http://127.0.0.1:8188
CAPOS_COMFYUI_CHECKPOINT=your_model.safetensors
CAPOS_COMFYUI_MODEL_LICENCE="see docs/MODEL_SELECTION.md"
# After validating a workflow locally, either clear template_only in JSON
# or point to your exported API workflow:
# CAPOS_COMFYUI_WORKFLOW_PATH=/absolute/path/to/workflow_api.json
CAPOS_COMFYUI_WORKFLOW=style-master-low-vram.json
```

### Test connection from CAPOS

```bash
python -c "from capos.generation.comfyui_backend import ComfyUIBackend; print(ComfyUIBackend().available())"
```

Or use Streamlit **Providers → TEST CONNECTION**.

### Smoke test

```bash
python scripts/phase2a_comfyui_smoke_and_style.py
```

Smoke images are tagged `PROVIDER_SMOKE_TEST` / non-canon.

### OOM troubleshooting

1. Confirm concurrency is 1  
2. Stay on SAFE 512  
3. Disable extra ControlNets/adapters  
4. Unload other GPU apps  
5. Let CAPOS OOM fallback try 448 / 384  
6. If still failing → `FAILED_RESOURCE_LIMIT` (do not fake success)

### Generation vs export resolution

Diffusion can be 512×512. Upscale selected assets later to 1024×1024 (or delivery size) as a **derivative** with provenance — never overwrite the source generation.
