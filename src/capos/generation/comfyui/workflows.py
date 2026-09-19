"""Load and parameterize ComfyUI API workflow templates."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

from capos.core.errors import ValidationError
from capos.core.paths import project_root
from capos.generation.comfyui.validate import validate_api_workflow


def workflows_dir(*, root: Path | None = None) -> Path:
    return (root or project_root()) / "workflows" / "comfyui"


def list_workflows(*, root: Path | None = None) -> list[str]:
    d = workflows_dir(root=root)
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.glob("*.json"))


def resolve_workflow_path(name: str | None = None, *, root: Path | None = None) -> Path:
    """Resolve workflow file: explicit path env > name > default ToonYou style master."""
    env_path = os.environ.get("CAPOS_COMFYUI_WORKFLOW_PATH")
    if env_path and Path(env_path).is_file():
        return Path(env_path)
    chosen = name or os.environ.get("CAPOS_COMFYUI_WORKFLOW") or "style-master-toonyou-beta6.json"
    path = Path(chosen)
    if path.is_file():
        return path
    path = workflows_dir(root=root) / chosen
    if path.is_file():
        return path
    raise ValidationError(
        f"ComfyUI workflow not found: {chosen}",
        hint=(
            "Export API format from ComfyUI Desktop (Save (API Format)) and place at "
            "workflows/comfyui/style-master-low-vram.json or set CAPOS_COMFYUI_WORKFLOW_PATH"
        ),
    )


def load_workflow(name: str | None = None, *, root: Path | None = None) -> dict[str, Any]:
    path = resolve_workflow_path(name, root=root)
    data = json.loads(path.read_text(encoding="utf-8"))
    if "prompt" in data and isinstance(data["prompt"], dict):
        meta = {k: v for k, v in data.items() if k != "prompt"}
        meta["source"] = str(path)
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
    sampler_name: str | None = None,
    scheduler: str | None = None,
    denoise: float | None = None,
    load_image_filename: str | None = None,
) -> dict[str, Any]:
    """Inject into nodes via capos_role tags or standard class_type heuristics.

    Always sets an explicit seed when provided — never leaves randomize-after-generate
    as the source of truth for CAPOS provenance.
    For img2img, pass load_image_filename (ComfyUI input folder name after upload).
    """
    prompt = copy.deepcopy(workflow_prompt)
    report = validate_api_workflow(prompt)
    roles = report["roles"]

    def _apply(nid: str, **updates: Any) -> None:
        node = prompt[nid]
        inputs = node.setdefault("inputs", {})
        inputs.update(updates)
        if isinstance(node.get("_meta"), dict):
            node.pop("_meta", None)

    for nid in roles.get("positive") or []:
        _apply(nid, text=positive)
    for nid in roles.get("negative") or []:
        _apply(nid, text=negative)
    for nid in roles.get("checkpoint") or []:
        if checkpoint:
            _apply(nid, ckpt_name=checkpoint)
    for nid in roles.get("size") or []:
        _apply(nid, width=int(width), height=int(height), batch_size=1)
    if load_image_filename:
        for nid in roles.get("load_image") or []:
            _apply(nid, image=load_image_filename)
    for nid in roles.get("sampler") or []:
        updates: dict[str, Any] = {}
        if seed is not None:
            updates["seed"] = int(seed)
        if steps is not None:
            updates["steps"] = int(steps)
        if cfg is not None:
            updates["cfg"] = float(cfg)
        if sampler_name is not None:
            updates["sampler_name"] = sampler_name
        if scheduler is not None:
            updates["scheduler"] = scheduler
        if denoise is not None:
            updates["denoise"] = float(denoise)
        if updates:
            _apply(nid, **updates)

    # Strip any remaining _meta so ComfyUI API does not reject unknown keys
    for _nid, node in prompt.items():
        if isinstance(node, dict):
            node.pop("_meta", None)
    return prompt


def workflow_is_configured(name: str | None = None, *, root: Path | None = None) -> tuple[bool, str]:
    try:
        data = load_workflow(name, root=root)
    except ValidationError as exc:
        return False, str(exc)
    meta = data.get("_meta") or {}
    if meta.get("template_only"):
        return (
            False,
            "Workflow is template_only — export/configure local checkpoint/nodes and clear template_only",
        )
    validation = validate_api_workflow(data["prompt"])
    if not validation["ok"]:
        return False, f"Workflow validation failed: missing={validation['missing_roles']}"
    if meta.get("requires_local_checkpoint") and not os.environ.get("CAPOS_COMFYUI_CHECKPOINT"):
        return False, "Set CAPOS_COMFYUI_CHECKPOINT to your local ComfyUI checkpoint filename"
    return True, "ok"


def describe_workflow(name: str | None = None, *, root: Path | None = None) -> dict[str, Any]:
    loaded = load_workflow(name, root=root)
    validation = validate_api_workflow(loaded["prompt"])
    meta = loaded.get("_meta") or {}
    return {
        "source": meta.get("source"),
        "workflow_id": meta.get("workflow_id"),
        "workflow_version": meta.get("workflow_version"),
        "template_only": bool(meta.get("template_only")),
        "operator_verified_topology": bool(meta.get("operator_verified_topology")),
        "validation": validation,
        "meta": {k: v for k, v in meta.items() if k != "prompt"},
    }
