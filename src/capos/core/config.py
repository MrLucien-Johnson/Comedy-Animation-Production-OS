"""Configuration loading."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from capos.core.paths import config_dir, project_root


def clear_config_cache() -> None:
    get_config.cache_clear()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def get_config(*, root: str | None = None) -> dict[str, Any]:
    base = Path(root).resolve() if root else project_root()
    cfg = config_dir(root=base)
    project = _load_json(cfg / "project.json")
    generation = _load_json(cfg / "generation.json")
    export = _load_json(cfg / "export.json")
    gates = _load_json(cfg / "production_gates.json")
    mock_env = os.environ.get("CAPOS_MOCK_GENERATION", "").strip() in {"1", "true", "True", "yes"}
    if mock_env:
        generation = {**generation, "use_mock_backend": True, "default_backend": "mock"}
    return {
        "project": project,
        "generation": generation,
        "export": export,
        "gates": gates,
        "root": str(base),
    }
