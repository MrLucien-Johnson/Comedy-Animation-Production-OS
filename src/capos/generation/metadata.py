"""Generation record I/O."""

from __future__ import annotations

import json
from pathlib import Path

from capos.core.paths import generations_dir
from capos.core.schemas import GenerationRecord


def save_record(record: GenerationRecord, *, root: Path | None = None) -> Path:
    base = generations_dir(root=root)
    dest = base / record.id
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / "record.json"
    record.touch()
    path.write_text(
        json.dumps(record.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    by_frame = base / "_by_frame" / record.frame_id
    by_frame.mkdir(parents=True, exist_ok=True)
    (by_frame / f"{record.id}.json").write_text(
        json.dumps({"id": record.id, "status": record.status.value}, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def load_record(record_id: str, *, root: Path | None = None) -> GenerationRecord:
    path = generations_dir(root=root) / record_id / "record.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return GenerationRecord.model_validate(data)


def list_records_for_frame(frame_id: str, *, root: Path | None = None) -> list[str]:
    by_frame = generations_dir(root=root) / "_by_frame" / frame_id
    if not by_frame.is_dir():
        return []
    return sorted(p.stem for p in by_frame.glob("*.json"))
