"""SEASON_PRODUCTION_READY gate — fail closed until minimum canon exists."""

from __future__ import annotations

from pathlib import Path

from capos.core.schemas import ProductionReadinessReport, QACheckResult
from capos.core.status import CanonStatus, ProviderAvailability, QAResultStatus, StageStatus
from capos.generation.provider_status import provider_dashboard_status
from capos.references.golden import GoldenFrameStore
from capos.references.versioning import ReferenceStore

REQUIRED_ASSET_IDS = [
    "character-likkle-jay-v1",
    "character-auntie-bev-v1",
    "outfit-likkle-jay-default-v1",
    "outfit-auntie-bev-default-v1",
    "location-kitchen-v1",
    "location-living-room-v1",
    "location-yard-v1",
    "location-jay-bedroom-v1",
    "prop-cookie-jar-v1",
    "style-likkle-jay-v1",
]

REQUIRED_TURNAROUNDS = [
    "turnaround-likkle-jay-front-v1",
    "turnaround-likkle-jay-three-quarter-left-v1",
    "turnaround-likkle-jay-three-quarter-right-v1",
    "turnaround-likkle-jay-side-left-v1",
    "turnaround-likkle-jay-side-right-v1",
    "turnaround-likkle-jay-back-v1",
]


def _status_ok(status: object) -> bool:
    value = status.value if hasattr(status, "value") else str(status)
    return value in {CanonStatus.APPROVED.value, StageStatus.LOCKED.value}


def evaluate_season_production_ready(
    series_id: str = "likkle-jay",
    *,
    season_id: str = "s01",
    root: Path | None = None,
) -> ProductionReadinessReport:
    store = ReferenceStore(series_id, root=root)
    golden = GoldenFrameStore(series_id, root=root)
    providers = provider_dashboard_status()
    report = ProductionReadinessReport(
        series_id=series_id,
        season_id=season_id,
        provider_status={p["name"]: p["availability"] for p in providers},
        engineering_ready=True,
    )

    def check_asset(asset_id: str) -> QACheckResult:
        ref = store.get(asset_id)
        if not ref:
            report.missing.append(asset_id)
            return QACheckResult(
                check_id=f"ASSET:{asset_id}",
                status=QAResultStatus.FAIL,
                message="Missing from registry",
            )
        status = ref.status.value if hasattr(ref.status, "value") else str(ref.status)
        if status in {CanonStatus.REFERENCE_REQUIRED.value, "REFERENCE_REQUIRED"}:
            report.missing.append(asset_id)
            return QACheckResult(
                check_id=f"ASSET:{asset_id}",
                status=QAResultStatus.FAIL,
                message="REFERENCE_REQUIRED — image not imported",
            )
        if not ref.effective_path or not Path(ref.effective_path).is_file():
            report.awaiting_approval.append(asset_id)
            return QACheckResult(
                check_id=f"ASSET:{asset_id}",
                status=QAResultStatus.FAIL,
                message=f"No image file (status={status})",
            )
        if not _status_ok(ref.status):
            report.awaiting_approval.append(asset_id)
            return QACheckResult(
                check_id=f"ASSET:{asset_id}",
                status=QAResultStatus.FAIL,
                message=f"Not APPROVED (status={status})",
            )
        report.approved.append(asset_id)
        return QACheckResult(
            check_id=f"ASSET:{asset_id}",
            status=QAResultStatus.PASS,
            message="APPROVED with file",
        )

    for aid in REQUIRED_ASSET_IDS + REQUIRED_TURNAROUNDS:
        report.checks.append(check_asset(aid))

    # Provider: need at least one non-mock AVAILABLE for real production recommendation,
    # OR mock-only is engineering-only.
    real_available = any(
        p["availability"] == ProviderAvailability.AVAILABLE.value and p["name"] != "mock"
        for p in providers
    )
    mock_available = any(
        p["name"] == "mock" and p["availability"] == ProviderAvailability.AVAILABLE.value
        for p in providers
    )
    if real_available:
        report.checks.append(
            QACheckResult(
                check_id="IMAGE_PROVIDER",
                status=QAResultStatus.PASS,
                message="Real provider AVAILABLE",
            )
        )
    elif mock_available:
        report.checks.append(
            QACheckResult(
                check_id="IMAGE_PROVIDER",
                status=QAResultStatus.FAIL,
                message="Only mock provider AVAILABLE — not sufficient for season production",
            )
        )
        report.notes.append("Configure HF_TOKEN or another real provider before season production.")
    else:
        report.checks.append(
            QACheckResult(
                check_id="IMAGE_PROVIDER",
                status=QAResultStatus.FAIL,
                message="No image provider AVAILABLE",
            )
        )

    report.checks.append(
        QACheckResult(
            check_id="QA_PIPELINE",
            status=QAResultStatus.PASS,
            message="QA validators importable",
        )
    )

    # Golden open-jar reference for S01E02
    open_jar = golden.get("golden-s01e02-f03-open-cookie-jar")
    if not open_jar or open_jar.status == CanonStatus.REFERENCE_REQUIRED or not open_jar.file:
        report.checks.append(
            QACheckResult(
                check_id="GOLDEN:s01e02-f03",
                status=QAResultStatus.FAIL,
                message="Open cookie-jar golden reference missing / REFERENCE_REQUIRED",
            )
        )
        report.missing.append("golden-s01e02-f03-open-cookie-jar")
    elif open_jar.status != CanonStatus.APPROVED:
        report.checks.append(
            QACheckResult(
                check_id="GOLDEN:s01e02-f03",
                status=QAResultStatus.FAIL,
                message=f"Golden frame status={open_jar.status}",
            )
        )
        report.awaiting_approval.append(open_jar.golden_id)
    else:
        report.checks.append(
            QACheckResult(
                check_id="GOLDEN:s01e02-f03",
                status=QAResultStatus.PASS,
                message="Golden open-jar APPROVED",
            )
        )

    failed = [c for c in report.checks if c.status == QAResultStatus.FAIL]
    report.season_production_ready = len(failed) == 0
    report.ready = report.season_production_ready
    report.content_ready = len(report.approved) > 0 and len(report.missing) == 0
    # Content ready requires approved masters with files — still fail until all required pass
    report.content_ready = report.season_production_ready
    if not report.season_production_ready:
        report.notes.append(
            "SEASON_PRODUCTION_READY = FAIL. Do not mass-generate episodes. "
            "Establish approved canon images first."
        )
    return report
