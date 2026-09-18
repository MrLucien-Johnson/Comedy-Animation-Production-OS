"""Load and parameterize ComfyUI API workflow templates."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

from capos.core.errors import ValidationError
from capos.core.paths import project_root


def workflows_dir(*, root: Path | None = None) -> Path:
    return (root or project_root()) / "workflows" / "comfyui"


def list_workflows(*, root: Path | None = None) -> list[str]:
    d = workflows_dir(root=root)
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.glob("*.json"))


def load_workflow(name: str, *, root: Path | None = None) -> dict[str, Any]:
    path = Path(name)
    if not path.is_file():
        path = workflows_dir(root=root) / name
    if not path.is_file():
        env = os.environ.get("CAPOS_COMFYUI_WORKFLOW_PATH")
        if env and Path(env).is_file():
            path = Path(env)
    if not path.is_file():
        raise ValidationError(
            f"ComfyUI workflow not found: {name}",
            hint="Install workflow JSON under workflows/comfyui/ or set CAPOS_COMFYUI_WORKFLOW_PATH",
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    if "prompt" in data and isinstance(data["prompt"], dict):
        meta = {k: v for k, v in data.items() if k != "prompt"}
        return {"_meta": meta, "prompt": data["prompt"]}
    return {"_meta": {"source": str(path)}, "prompt": data}


def inject_basic_params(
    workflow_prompt: dict[str, Any],
    *,
    positive: str,
    negative: str = "",
    seed: int | None = None,
    width: int = 512,
    height: int = 512,
    steps: int | None = None,
    cfg: float | None = None,
    checkpoint: str | None = None,
) -> dict[str, Any]:
    """Inject into nodes tagged with `_meta.capos_role`."""
    prompt = copy.deepcopy(workflow_prompt)
    for _nid, node in prompt.items():
        if not isinstance(node, dict):
            continue
        role = (node.get("_meta") or {}).get("capos_role") or ""
        inputs = node.setdefault("inputs", {})
        if role == "positive":
            inputs["text"] = positive
        elif role == "negative":
            inputs["text"] = negative
        elif role == "seed":
            if seed is not None:
                inputs["seed"] = int(seed)
        elif role == "sampler":
            if seed is not None and "seed" in inputs:
                inputs["seed"] = int(seed)
            if steps is not None and "steps" in inputs:
                inputs["steps"] = int(steps)
            if cfg is not None and "cfg" in inputs:
                inputs["cfg"] = float(cfg)
        elif role == "size":
            inputs["width"] = int(width)
            inputs["height"] = int(height)
        elif role == "checkpoint" and checkpoint:
            inputs["ckpt_name"] = checkpoint
        elif role == "steps" and steps is not None:
            inputs["steps"] = int(steps)
        elif role == "cfg" and cfg is not None:
            inputs["cfg"] = float(cfg)
        node.pop("_meta", None)
    return prompt


def workflow_is_configured(name: str, *, root: Path | None = None) -> tuple[bool, str]:
    try:
        data = load_workflow(name, root=root)
    except ValidationError as exc:
        return False, str(exc)
    meta = data.get("_meta") or {}
    if meta.get("template_only"):
        return (
            False,
            "Workflow is template_only — configure local checkpoint/nodes and clear template_only",
        )
    if meta.get("requires_local_checkpoint") and not os.environ.get("CAPOS_COMFYUI_CHECKPOINT"):
        return False, "Set CAPOS_COMFYUI_CHECKPOINT to your local ComfyUI checkpoint filename"
    return True, "ok"
