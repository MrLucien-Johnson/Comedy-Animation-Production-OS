"""Project path resolution."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

_ENV_ROOT = "CAPOS_PROJECT_ROOT"


def clear_path_cache() -> None:
    project_root.cache_clear()


@lru_cache(maxsize=1)
def project_root() -> Path:
    env = os.environ.get(_ENV_ROOT)
    if env:
        return Path(env).resolve()

    here = Path.cwd().resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "pyproject.toml").is_file() and (candidate / "config").is_dir():
            return candidate
        if (candidate / "config" / "project.json").is_file():
            return candidate
        if (candidate / ".git").exists() and (candidate / "series").is_dir():
            return candidate
    return here


def resolve_path(path: str | Path, *, root: Path | None = None) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    return (root or project_root()) / p


def series_dir(series_id: str, *, root: Path | None = None) -> Path:
    return (root or project_root()) / "series" / series_id


def assets_dir(*, root: Path | None = None) -> Path:
    return (root or project_root()) / "assets"


def generations_dir(*, root: Path | None = None) -> Path:
    return assets_dir(root=root) / "generations"


def approved_dir(*, root: Path | None = None) -> Path:
    return assets_dir(root=root) / "approved"


def rejected_dir(*, root: Path | None = None) -> Path:
    return assets_dir(root=root) / "rejected"


def exports_dir(*, root: Path | None = None) -> Path:
    return assets_dir(root=root) / "exports"


def config_dir(*, root: Path | None = None) -> Path:
    return (root or project_root()) / "config"


def prompts_dir(*, root: Path | None = None) -> Path:
    return (root or project_root()) / "prompts"
