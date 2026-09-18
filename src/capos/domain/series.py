"""Series / season / episode domain loaders."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from capos.core.errors import ValidationError
from capos.core.paths import series_dir
from capos.core.schemas import EpisodeBrief, ScriptDocument, StoryboardBeat
from capos.core.status import StageStatus


class SeriesConfig(BaseModel):
    series_id: str
    title: str
    slug: str
    logline: str = ""
    visual_style: dict[str, Any] = Field(default_factory=dict)
    watermark: str = "MRLUCIENJOHNSON"
    aspect_ratio_master: str = "1:1"
    characters: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    props: list[str] = Field(default_factory=list)
    seasons: list[str] = Field(default_factory=list)
    status: StageStatus = StageStatus.DRAFT


class SeasonConfig(BaseModel):
    season_id: str
    series_id: str
    number: int
    title: str
    episodes: list[str] = Field(default_factory=list)
    status: StageStatus = StageStatus.DRAFT


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValidationError(f"Missing JSON: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any] | BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = data.model_dump(mode="json") if isinstance(data, BaseModel) else data
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_series(series_id: str, *, root: Path | None = None) -> SeriesConfig:
    path = series_dir(series_id, root=root) / "series.json"
    return SeriesConfig.model_validate(load_json(path))


def load_episode_brief(
    series_id: str, episode_id: str, *, root: Path | None = None
) -> EpisodeBrief:
    path = series_dir(series_id, root=root) / "episodes" / episode_id / "brief.json"
    return EpisodeBrief.model_validate(load_json(path))


def load_script(series_id: str, episode_id: str, *, root: Path | None = None) -> ScriptDocument:
    path = series_dir(series_id, root=root) / "episodes" / episode_id / "script.json"
    return ScriptDocument.model_validate(load_json(path))


def load_storyboard(
    series_id: str, episode_id: str, *, root: Path | None = None
) -> list[StoryboardBeat]:
    path = series_dir(series_id, root=root) / "episodes" / episode_id / "storyboard.json"
    raw = load_json(path)
    beats = raw.get("beats", raw if isinstance(raw, list) else [])
    return [StoryboardBeat.model_validate(b) for b in beats]


def list_series(*, root: Path | None = None) -> list[str]:
    base = (root or Path(".")) if root else None
    from capos.core.paths import project_root

    series_root = (base or project_root()) / "series"
    if not series_root.is_dir():
        return []
    return sorted(
        p.name for p in series_root.iterdir() if p.is_dir() and (p / "series.json").is_file()
    )
