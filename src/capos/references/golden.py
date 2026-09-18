"""Golden frame system + REFERENCE_REQUIRED workflows."""

from __future__ import annotations

import json
from pathlib import Path

from capos.core.errors import ValidationError
from capos.core.paths import series_dir
from capos.core.schemas import GoldenFrameRecord, utcnow
from capos.core.status import CanonStatus


def golden_index_path(series_id: str, *, root: Path | None = None) -> Path:
    return series_dir(series_id, root=root) / "golden" / "index.json"


class GoldenFrameStore:
    def __init__(self, series_id: str, *, root: Path | None = None) -> None:
        self.series_id = series_id
        self.root = root
        self.path = golden_index_path(series_id, root=root)

    def _load(self) -> dict:
        if not self.path.is_file():
            return {"frames": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    def get(self, golden_id: str) -> GoldenFrameRecord | None:
        raw = self._load().get("frames", {}).get(golden_id)
        return GoldenFrameRecord.model_validate(raw) if raw else None

    def list_all(self) -> list[GoldenFrameRecord]:
        frames = self._load().get("frames", {})
        return sorted(
            [GoldenFrameRecord.model_validate(v) for v in frames.values()],
            key=lambda g: g.golden_id,
        )

    def register(self, record: GoldenFrameRecord) -> GoldenFrameRecord:
        data = self._load()
        data.setdefault("frames", {})[record.golden_id] = record.model_dump(mode="json")
        self._save(data)
        return record

    def mark_reference_required(
        self,
        golden_id: str,
        *,
        reason: str,
        episode_id: str | None = None,
        frame_id: str | None = None,
        governs: list[str] | None = None,
        notes: str = "",
    ) -> GoldenFrameRecord:
        existing = self.get(golden_id)
        record = existing or GoldenFrameRecord(
            golden_id=golden_id,
            series_id=self.series_id,
            episode_id=episode_id,
            frame_id=frame_id,
        )
        record.status = CanonStatus.REFERENCE_REQUIRED
        record.reference_required_reason = reason
        record.file = None
        if governs is not None:
            record.governs = governs
        if notes:
            record.notes = notes
        if episode_id:
            record.episode_id = episode_id
        if frame_id:
            record.frame_id = frame_id
        return self.register(record)

    def attach_and_candidate(self, golden_id: str, file_path: str | Path) -> GoldenFrameRecord:
        record = self.get(golden_id)
        if not record:
            raise ValidationError(f"Unknown golden frame {golden_id}")
        path = Path(file_path)
        if not path.is_file():
            raise ValidationError(f"Golden frame file missing: {path}")
        record.file = str(path)
        record.status = CanonStatus.CANDIDATE
        record.reference_required_reason = None
        return self.register(record)

    def lock_as_golden(self, golden_id: str) -> GoldenFrameRecord:
        record = self.get(golden_id)
        if not record:
            raise ValidationError(f"Unknown golden frame {golden_id}")
        if not record.file or not Path(record.file).is_file():
            raise ValidationError(
                f"Cannot lock golden {golden_id} without an image file",
                hint="Upload/select the reference image first (REFERENCE_REQUIRED).",
            )
        record.status = CanonStatus.APPROVED
        record.approved_at = utcnow()
        return self.register(record)

    def ensure_s01e02_open_jar_placeholder(self) -> GoldenFrameRecord:
        """
        Episode 2 Frame 3 is the desired OPEN cookie-jar continuity master.
        If the original image is not in-repo, record REFERENCE_REQUIRED — never claim import.
        """
        gid = "golden-s01e02-f03-open-cookie-jar"
        existing = self.get(gid)
        if existing and existing.file and Path(existing.file).is_file():
            return existing
        return self.mark_reference_required(
            gid,
            reason=(
                "S01E02 Frame 3 open-cookie-jar visual master is not present in this repository. "
                "User must upload/select the approved open-jar reference before it can govern production."
            ),
            episode_id="s01e02",
            frame_id="s01e02_f03",
            governs=[
                "prop-cookie-jar open state",
                "lid beside jar",
                "kitchen composition",
                "jar scale",
                "jar position LEFT_COUNTER",
            ],
            notes="Desired OPEN configuration continuity for Di Cookie Jar from frame 3 onward.",
        )
