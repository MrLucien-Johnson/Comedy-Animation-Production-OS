"""Schema and constant tests."""

from __future__ import annotations

import pytest

from capos.core.schemas import (
    COOKIE_LABEL_EXACT,
    WATERMARK_EXACT,
    FrameManifest,
    QACheckResult,
    QAReport,
)
from capos.core.status import FrameType, QAResultStatus, StageStatus
from capos.qa.validators import assert_cookie_label_exact, assert_watermark_exact


def test_watermark_exact():
    assert WATERMARK_EXACT == "MRLUCIENJOHNSON"
    assert_watermark_exact("MRLUCIENJOHNSON")
    with pytest.raises(AssertionError):
        assert_watermark_exact("MRLUCIENJONSSON")
    with pytest.raises(AssertionError):
        assert_watermark_exact("MR LUCIEN JOHNSON")


def test_cookie_label_exact():
    assert COOKIE_LABEL_EXACT == "COOKIES"
    assert_cookie_label_exact("COOKIES")
    with pytest.raises(AssertionError):
        assert_cookie_label_exact("COOKIE")


def test_frame_manifest_roundtrip():
    frame = FrameManifest(
        frame_id="s01e02_f01",
        series_id="likkle-jay",
        season_id="s01",
        episode_id="s01e02",
        frame_type=FrameType.KEYFRAME,
    )
    data = frame.model_dump(mode="json")
    again = FrameManifest.model_validate(data)
    assert again.frame_id == "s01e02_f01"
    assert again.status == StageStatus.DRAFT


def test_qa_report_export_gate():
    report = QAReport(
        target_id="f1",
        checks=[
            QACheckResult(check_id="A", status=QAResultStatus.PASS),
            QACheckResult(check_id="B", status=QAResultStatus.NOT_CHECKED),
        ],
    )
    report.summarize()
    assert report.overall == QAResultStatus.NOT_CHECKED
    assert report.can_export is False
    report.human_override = True
    assert report.can_export is True
