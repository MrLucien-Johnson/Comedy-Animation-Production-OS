"""Shared fixtures."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from capos.core.config import clear_config_cache
from capos.core.paths import clear_path_cache


@pytest.fixture()
def tmp_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "capos_proj"
    # Copy minimal tree from real project
    src = Path(__file__).resolve().parents[1]
    for name in ("config", "series", "workflows"):
        shutil.copytree(src / name, root / name)
    for d in (
        "assets/generations",
        "assets/approved",
        "assets/rejected",
        "assets/exports",
        "prompts",
    ):
        (root / d).mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CAPOS_PROJECT_ROOT", str(root))
    monkeypatch.setenv("CAPOS_MOCK_GENERATION", "1")
    clear_path_cache()
    clear_config_cache()
    yield root
    clear_path_cache()
    clear_config_cache()
