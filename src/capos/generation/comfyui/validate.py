"""Validate ComfyUI API-format workflows for CAPOS injection points."""

from __future__ import annotations

from typing import Any

REQUIRED_ROLES = (
    "checkpoint",
    "positive",
    "negative",
    "seed",
    "size",
    "sampler",
    "output",
)


def _roles_from_prompt(prompt: dict[str, Any]) -> dict[str, list[str]]:
    """Map CAPOS roles → node ids (explicit _meta.capos_role or class_type heuristics)."""
    roles: dict[str, list[str]] = {r: [] for r in REQUIRED_ROLES}
    clip_encode_ids: list[str] = []
    for nid, node in prompt.items():
        if not isinstance(node, dict):
            continue
        role = (node.get("_meta") or {}).get("capos_role") or ""
        ctype = node.get("class_type") or ""
        if role == "checkpoint" or ctype == "CheckpointLoaderSimple":
            roles["checkpoint"].append(nid)
        elif role == "positive":
            roles["positive"].append(nid)
        elif role == "negative":
            roles["negative"].append(nid)
        elif ctype == "CLIPTextEncode":
            clip_encode_ids.append(nid)
        elif role == "size" or ctype == "EmptyLatentImage":
            roles["size"].append(nid)
        elif role in {"sampler", "seed"} or ctype == "KSampler":
            roles["sampler"].append(nid)
            roles["seed"].append(nid)
        elif role == "output" or ctype == "SaveImage":
            roles["output"].append(nid)

    # Heuristic: first CLIPTextEncode = positive, second = negative (standard txt2img API export)
    if not roles["positive"] and clip_encode_ids:
        roles["positive"].append(clip_encode_ids[0])
    if not roles["negative"] and len(clip_encode_ids) > 1:
        roles["negative"].append(clip_encode_ids[1])
    return roles


def validate_api_workflow(prompt: dict[str, Any]) -> dict[str, Any]:
    """Return validation report; ok=False if required injection points missing."""
    roles = _roles_from_prompt(prompt)
    missing = [r for r in REQUIRED_ROLES if not roles.get(r)]
    checks: dict[str, bool] = {}
    for role, nids in roles.items():
        if not nids:
            checks[role] = False
            continue
        node = prompt[nids[0]]
        inputs = node.get("inputs") or {}
        if role == "checkpoint":
            checks[role] = "ckpt_name" in inputs
        elif role in {"positive", "negative"}:
            checks[role] = "text" in inputs
        elif role == "seed":
            checks[role] = "seed" in inputs
        elif role == "size":
            checks[role] = "width" in inputs and "height" in inputs
        elif role == "sampler":
            checks[role] = all(k in inputs for k in ("seed", "steps", "cfg", "sampler_name", "scheduler"))
        elif role == "output":
            checks[role] = "images" in inputs
        else:
            checks[role] = True

    ok = not missing and all(checks.values())
    return {
        "ok": ok,
        "roles": roles,
        "checks": checks,
        "missing_roles": missing,
        "configurable": {
            "checkpoint": checks.get("checkpoint", False),
            "positive_prompt": checks.get("positive", False),
            "negative_prompt": checks.get("negative", False),
            "seed": checks.get("seed", False),
            "width": checks.get("size", False),
            "height": checks.get("size", False),
            "steps": checks.get("sampler", False),
            "cfg": checks.get("sampler", False),
            "sampler": checks.get("sampler", False),
            "scheduler": checks.get("sampler", False),
            "output": checks.get("output", False),
        },
    }
