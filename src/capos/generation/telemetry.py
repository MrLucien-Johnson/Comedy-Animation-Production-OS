"""Generation telemetry + upscale derivative provenance (non-sensitive)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from capos.core.paths import project_root
from capos.core.schemas import utcnow
from capos.production.storage import sha256_file


def telemetry_dir(*, root: Path | None = None) -> Path:
    return (root or project_root()) / "logs" / "generation_telemetry"


def record_generation_telemetry(event: dict[str, Any], *, root: Path | None = None) -> Path:
    """Record NON-SENSITIVE generation metrics only."""
    allowed = {
        "backend",
        "model",
        "workflow",
        "resolution",
        "width",
        "height",
        "duration_ms",
        "success",
        "failure_kind",
        "oom",
        "retry_count",
        "peak_vram_mb",
        "seed",
        "profile",
        "candidate_id",
        "batch_id",
        "checksum",
        "smoke_test",
        "non_production",
    }
    clean = {k: event[k] for k in allowed if k in event}
    clean["recorded_at"] = utcnow().isoformat()
    d = telemetry_dir(root=root)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{utcnow().strftime('%Y%m%dT%H%M%SZ')}_{clean.get('candidate_id', 'job')}.json"
    path.write_text(json.dumps(clean, indent=2) + "\n", encoding="utf-8")
    return path


def register_upscaled_derivative(
    *,
    source_path: Path,
    upscaled_path: Path,
    series_id: str = "likkle-jay",
    root: Path | None = None,
    method: str = "local_upscale",
) -> dict[str, Any]:
    """Preserve SOURCE_GENERATION; store UPSCALED_DERIVATIVE with provenance link."""
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if not upscaled_path.is_file():
        raise FileNotFoundError(upscaled_path)
    base = (root or project_root()) / "production" / series_id / "derivatives" / "upscaled"
    base.mkdir(parents=True, exist_ok=True)
    dest = base / upscaled_path.name
    if dest.resolve() != upscaled_path.resolve():
        dest.write_bytes(upscaled_path.read_bytes())
    meta = {
        "kind": "UPSCALED_DERIVATIVE",
        "source_generation": str(source_path),
        "source_checksum": sha256_file(source_path),
        "upscaled_file": str(dest),
        "upscaled_checksum": sha256_file(dest),
        "method": method,
        "created_at": utcnow().isoformat(),
    }
    (dest.with_suffix(dest.suffix + ".provenance.json")).write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    return meta
