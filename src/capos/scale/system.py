"""Scale system — normalized relative proportions (Jay height = 1.0)."""

from __future__ import annotations

import json
from pathlib import Path

from capos.core.errors import ValidationError
from capos.core.paths import series_dir
from capos.core.schemas import QACheckResult, ScaleManifest, ScaleUnit
from capos.core.status import QAResultStatus

LIKKLE_JAY_DEFAULT_SCALE = ScaleManifest(
    series_id="likkle-jay",
    baseline_character="likkle-jay",
    baseline_unit_name="likkle-jay-height",
    units=[
        ScaleUnit(name="likkle-jay-height", relative_to="likkle-jay-height", value=1.0),
        ScaleUnit(
            name="counter-height",
            relative_to="likkle-jay-height",
            value=0.55,
            notes="Kitchen counter top relative to Jay standing height",
        ),
        ScaleUnit(
            name="cookie-jar-height",
            relative_to="counter-height",
            value=0.35,
            notes="Jar must not dominate the counter; derive from this ratio",
        ),
        ScaleUnit(
            name="cookie-diameter",
            relative_to="cookie-jar-height",
            value=0.28,
            notes="Cookies small relative to jar opening — never oversized",
        ),
        ScaleUnit(
            name="fridge-height",
            relative_to="likkle-jay-height",
            value=1.35,
            notes="Cream fridge on RIGHT",
        ),
        ScaleUnit(
            name="auntie-bev-height",
            relative_to="likkle-jay-height",
            value=1.15,
            notes="Adult stout silhouette taller than Jay",
        ),
    ],
)


def scale_path(series_id: str, *, root: Path | None = None) -> Path:
    return series_dir(series_id, root=root) / "scale" / "relative_scale.json"


def load_scale(series_id: str, *, root: Path | None = None) -> ScaleManifest:
    path = scale_path(series_id, root=root)
    if not path.is_file():
        if series_id == "likkle-jay":
            return LIKKLE_JAY_DEFAULT_SCALE
        raise ValidationError(f"Missing scale manifest: {path}")
    return ScaleManifest.model_validate(json.loads(path.read_text(encoding="utf-8")))


def save_scale(manifest: ScaleManifest, *, root: Path | None = None) -> Path:
    path = scale_path(manifest.series_id, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def unit_value(manifest: ScaleManifest, name: str) -> float:
    for u in manifest.units:
        if u.name == name:
            return u.value
    raise ValidationError(f"Unknown scale unit: {name}")


def absolute_vs_baseline(manifest: ScaleManifest, name: str) -> float:
    """Resolve unit to baseline (Jay height) by walking relative_to chain."""
    by_name = {u.name: u for u in manifest.units}
    if name not in by_name:
        raise ValidationError(f"Unknown scale unit: {name}")
    visited: set[str] = set()
    current = name
    product = 1.0
    while True:
        if current in visited:
            raise ValidationError(f"Scale cycle involving {name}")
        visited.add(current)
        unit = by_name[current]
        product *= unit.value
        if (
            unit.relative_to == manifest.baseline_unit_name
            and unit.name == manifest.baseline_unit_name
        ):
            return product
        if unit.relative_to == manifest.baseline_unit_name:
            return product
        if unit.relative_to not in by_name:
            raise ValidationError(f"Broken relative_to: {unit.relative_to}")
        current = unit.relative_to


def compile_scale_prompt_block(manifest: ScaleManifest) -> str:
    lines = [
        "RELATIVE SCALE LOCK (normalized; do not invent giant props):",
        f"Baseline unit: {manifest.baseline_unit_name} = 1.0 ({manifest.baseline_character})",
    ]
    for u in manifest.units:
        abs_v = absolute_vs_baseline(manifest, u.name)
        lines.append(
            f"- {u.name}: {u.value} × {u.relative_to} (≈ {abs_v:.3f} × baseline). {u.notes}".strip()
        )
    lines.append("Cookie jar and cookies must obey cookie-jar-height and cookie-diameter ratios.")
    return "\n".join(lines)


def check_scale_ratio_drift(
    expected: float,
    observed: float | None,
    *,
    tolerance: float = 0.25,
    check_id: str = "SCALE_CHECK",
) -> QACheckResult:
    """
    Compare expected vs observed ratio when observation is available.
    Without a measured observation, return NOT_CHECKED — never fake PASS.
    """
    if observed is None:
        return QACheckResult(
            check_id=check_id,
            status=QAResultStatus.NOT_CHECKED,
            message="No measured scale observation available",
            details={"expected": expected},
        )
    if expected <= 0:
        return QACheckResult(
            check_id=check_id,
            status=QAResultStatus.FAIL,
            message="Invalid expected scale",
        )
    drift = abs(observed - expected) / expected
    if drift > tolerance:
        return QACheckResult(
            check_id=check_id,
            status=QAResultStatus.FAIL,
            message=f"Scale drift {drift:.2%} exceeds tolerance {tolerance:.0%}",
            details={"expected": expected, "observed": observed, "drift": drift},
        )
    return QACheckResult(
        check_id=check_id,
        status=QAResultStatus.REQUIRES_HUMAN_REVIEW,
        message="Heuristic scale within tolerance — human review still required for identity",
        details={"expected": expected, "observed": observed, "drift": drift},
    )
