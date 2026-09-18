"""Approval workflow — never silently overwrite approved assets."""

from __future__ import annotations

import shutil
from pathlib import Path

from capos.core.errors import ValidationError
from capos.core.paths import approved_dir, rejected_dir
from capos.core.schemas import GenerationRecord
from capos.core.status import StageStatus
from capos.generation.metadata import load_record, save_record


class ApprovalWorkflow:
    def __init__(self, *, root: Path | None = None) -> None:
        self.root = root

    def approve(
        self,
        record_id: str,
        *,
        force: bool = False,
        dest_name: str | None = None,
    ) -> GenerationRecord:
        record = load_record(record_id, root=self.root)
        if record.status == StageStatus.APPROVED and not force:
            raise ValidationError(
                f"Record '{record_id}' is already APPROVED",
                hint="Pass force=True to replace deliberately.",
            )
        if record.status == StageStatus.LOCKED and not force:
            raise ValidationError(f"Record '{record_id}' is LOCKED")
        if not record.output_path:
            raise ValidationError(f"Record '{record_id}' has no output_path")

        src = Path(record.output_path)
        if not src.is_file() and self.root:
            candidate = Path(self.root) / record.output_path
            if candidate.is_file():
                src = candidate
        if not src.is_file():
            raise ValidationError(f"Generated file missing: {record.output_path}")

        dest_dir = approved_dir(root=self.root)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / (dest_name or src.name)
        if dest.exists() and not force:
            dest = dest_dir / f"{dest.stem}_{record.id[:8]}{dest.suffix}"

        shutil.copy2(src, dest)
        record.status = StageStatus.APPROVED
        record.approved_path = str(dest)
        save_record(record, root=self.root)
        return record

    def reject(self, record_id: str, *, reason: str = "") -> GenerationRecord:
        record = load_record(record_id, root=self.root)
        if record.status in {StageStatus.APPROVED, StageStatus.LOCKED}:
            raise ValidationError(
                f"Cannot reject {record.status} record without unapprove",
            )
        if record.output_path:
            src = Path(record.output_path)
            if src.is_file():
                dest_dir = rejected_dir(root=self.root)
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest_dir / src.name)
        record.status = StageStatus.REJECTED
        if reason:
            record.error = reason
        save_record(record, root=self.root)
        return record

    def lock(self, record_id: str) -> GenerationRecord:
        record = load_record(record_id, root=self.root)
        if record.status != StageStatus.APPROVED:
            raise ValidationError("Only APPROVED records can be LOCKED as canon")
        record.status = StageStatus.LOCKED
        save_record(record, root=self.root)
        return record
