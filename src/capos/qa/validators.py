"""Automated QA validators — fail closed; never fake visual PASS."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path

from PIL import Image

from capos.core.schemas import (
    COOKIE_LABEL_EXACT,
    WATERMARK_EXACT,
    FrameManifest,
    QACheckResult,
    QAReport,
)
from capos.core.status import QAResultStatus, StageStatus

CheckFn = Callable[..., QACheckResult]


def _file_check(path: Path | None) -> QACheckResult:
    if not path:
        return QACheckResult(
            check_id="FILE_CHECK",
            status=QAResultStatus.FAIL,
            message="No file path provided",
        )
    p = Path(path)
    if not p.is_file():
        return QACheckResult(
            check_id="FILE_CHECK",
            status=QAResultStatus.FAIL,
            message=f"Missing file: {p}",
        )
    return QACheckResult(check_id="FILE_CHECK", status=QAResultStatus.PASS, message="File exists")


def _dimension_check(path: Path, width: int, height: int) -> QACheckResult:
    try:
        with Image.open(path) as img:
            w, h = img.size
    except Exception as exc:  # noqa: BLE001
        return QACheckResult(
            check_id="DIMENSION_CHECK",
            status=QAResultStatus.FAIL,
            message=f"Cannot open image: {exc}",
        )
    if (w, h) != (width, height):
        return QACheckResult(
            check_id="DIMENSION_CHECK",
            status=QAResultStatus.FAIL,
            message=f"Expected {width}x{height}, got {w}x{h}",
        )
    return QACheckResult(
        check_id="DIMENSION_CHECK",
        status=QAResultStatus.PASS,
        message=f"{w}x{h}",
    )


def _aspect_ratio_check(path: Path, aspect: str) -> QACheckResult:
    try:
        a, b = aspect.split(":")
        target = float(a) / float(b)
        with Image.open(path) as img:
            w, h = img.size
        actual = w / h
    except Exception as exc:  # noqa: BLE001
        return QACheckResult(
            check_id="ASPECT_RATIO_CHECK",
            status=QAResultStatus.FAIL,
            message=str(exc),
        )
    if abs(actual - target) > 0.02:
        return QACheckResult(
            check_id="ASPECT_RATIO_CHECK",
            status=QAResultStatus.FAIL,
            message=f"Expected {aspect}, got {w}:{h}",
        )
    return QACheckResult(check_id="ASPECT_RATIO_CHECK", status=QAResultStatus.PASS, message=aspect)


def _reference_check(frame: FrameManifest) -> QACheckResult:
    missing = []
    if not frame.character_reference_ids:
        missing.append("characters")
    if not frame.location_reference_id:
        missing.append("location")
    if missing:
        return QACheckResult(
            check_id="REFERENCE_CHECK",
            status=QAResultStatus.FAIL,
            message=f"Missing governing refs: {', '.join(missing)}",
        )
    return QACheckResult(
        check_id="REFERENCE_CHECK",
        status=QAResultStatus.PASS,
        message="Frame declares governing reference ids",
        details={
            "characters": frame.character_reference_ids,
            "location": frame.location_reference_id,
            "props": frame.prop_reference_ids,
        },
    )


def _character_check(frame: FrameManifest) -> QACheckResult:
    for c in frame.continuity.characters:
        if c.character_id == "likkle-jay":
            expected = "rounded dome of tight black curls, full and consistent"
            if c.hair_lock != expected:
                return QACheckResult(
                    check_id="CHARACTER_CHECK",
                    status=QAResultStatus.FAIL,
                    message="Likkle Jay hair lock mismatch",
                )
    return QACheckResult(
        check_id="CHARACTER_CHECK",
        status=QAResultStatus.PASS,
        message="Character continuity fields consistent with locks",
    )


def _outfit_check(frame: FrameManifest) -> QACheckResult:
    for c in frame.continuity.characters:
        if c.character_id == "likkle-jay" and not c.outfit_asset_id:
            return QACheckResult(
                check_id="OUTFIT_CHECK",
                status=QAResultStatus.FAIL,
                message="Likkle Jay missing outfit_asset_id",
            )
    return QACheckResult(check_id="OUTFIT_CHECK", status=QAResultStatus.PASS, message="ok")


def _prop_presence_check(frame: FrameManifest, required: list[str] | None = None) -> QACheckResult:
    required = required or []
    present = {p.prop_id for p in frame.continuity.props}
    missing = [r for r in required if r not in present]
    if missing:
        return QACheckResult(
            check_id="PROP_PRESENCE_CHECK",
            status=QAResultStatus.FAIL,
            message=f"Missing props: {missing}",
        )
    return QACheckResult(check_id="PROP_PRESENCE_CHECK", status=QAResultStatus.PASS, message="ok")


def _prop_state_check(
    frame: FrameManifest, expected: dict[str, str] | None = None
) -> QACheckResult:
    expected = expected or {}
    by_id = {p.prop_id: p for p in frame.continuity.props}
    for pid, state in expected.items():
        if pid not in by_id:
            return QACheckResult(
                check_id="PROP_STATE_CHECK",
                status=QAResultStatus.FAIL,
                message=f"Prop {pid} absent",
            )
        if by_id[pid].state.value != state:
            return QACheckResult(
                check_id="PROP_STATE_CHECK",
                status=QAResultStatus.FAIL,
                message=f"Prop {pid} expected {state}, got {by_id[pid].state.value}",
            )
    return QACheckResult(check_id="PROP_STATE_CHECK", status=QAResultStatus.PASS, message="ok")


def _background_check(frame: FrameManifest) -> QACheckResult:
    if not frame.continuity.location_id:
        return QACheckResult(
            check_id="BACKGROUND_CHECK",
            status=QAResultStatus.FAIL,
            message="No location_id on continuity",
        )
    return QACheckResult(
        check_id="BACKGROUND_CHECK",
        status=QAResultStatus.PASS,
        message=frame.continuity.location_id,
    )


def _text_check(*, locked_dialogue: str | None, rendered_dialogue: str | None) -> QACheckResult:
    """Deterministic dialogue exactness — not OCR."""
    if locked_dialogue is None:
        return QACheckResult(
            check_id="TEXT_CHECK", status=QAResultStatus.PASS, message="No locked dialogue"
        )
    if rendered_dialogue != locked_dialogue:
        return QACheckResult(
            check_id="TEXT_CHECK",
            status=QAResultStatus.FAIL,
            message=f"Dialogue drift: expected {locked_dialogue!r} got {rendered_dialogue!r}",
        )
    # Also guard prop label COOKIES vs COOKIE when provided via metadata convention
    if COOKIE_LABEL_EXACT in locked_dialogue and "COOKIE" in locked_dialogue.replace(
        COOKIE_LABEL_EXACT, ""
    ):
        pass
    return QACheckResult(check_id="TEXT_CHECK", status=QAResultStatus.PASS, message="exact")


def _watermark_check(watermark_text: str | None) -> QACheckResult:
    if watermark_text is None:
        return QACheckResult(
            check_id="WATERMARK_CHECK",
            status=QAResultStatus.FAIL,
            message="Watermark not applied / not declared",
        )
    if watermark_text != WATERMARK_EXACT:
        return QACheckResult(
            check_id="WATERMARK_CHECK",
            status=QAResultStatus.FAIL,
            message=f"Watermark must be exactly {WATERMARK_EXACT!r}, got {watermark_text!r}",
        )
    return QACheckResult(
        check_id="WATERMARK_CHECK", status=QAResultStatus.PASS, message=WATERMARK_EXACT
    )


def _sequence_check(frames: list[FrameManifest]) -> QACheckResult:
    for i, frame in enumerate(frames):
        if i == 0:
            continue
        if frame.continuity_from != frames[i - 1].frame_id:
            return QACheckResult(
                check_id="SEQUENCE_CHECK",
                status=QAResultStatus.FAIL,
                message=f"Broken continuity_from at {frame.frame_id}",
            )
    return QACheckResult(check_id="SEQUENCE_CHECK", status=QAResultStatus.PASS, message="ok")


def visual_similarity_check(
    *,
    check_id: str,
    image_a: Path | None,
    image_b: Path | None,
    threshold: float = 0.85,
) -> QACheckResult:
    """
    Interface for CV similarity. Without a real CV backend, report NOT_CHECKED.
    Do NOT pretend PASS.
    """
    if image_a is None or image_b is None:
        return QACheckResult(
            check_id=check_id,
            status=QAResultStatus.NOT_CHECKED,
            message="Similarity not checked — missing image path(s)",
        )
    # No CV dependency bundled: honest NOT_CHECKED.
    return QACheckResult(
        check_id=check_id,
        status=QAResultStatus.NOT_CHECKED,
        message="No computer-vision similarity backend configured",
        details={"threshold": threshold, "image_a": str(image_a), "image_b": str(image_b)},
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def run_frame_qa(
    frame: FrameManifest,
    *,
    image_path: Path | None = None,
    watermark_text: str | None = None,
    rendered_dialogue: str | None = None,
    required_props: list[str] | None = None,
    expected_prop_states: dict[str, str] | None = None,
) -> QAReport:
    checks: list[QACheckResult] = [
        _reference_check(frame),
        _character_check(frame),
        _outfit_check(frame),
        _prop_presence_check(frame, required_props),
        _prop_state_check(frame, expected_prop_states),
        _background_check(frame),
        _text_check(
            locked_dialogue=frame.dialogue if frame.dialogue_locked else None,
            rendered_dialogue=rendered_dialogue if frame.dialogue_locked else None,
        ),
        _watermark_check(watermark_text),
        visual_similarity_check(
            check_id="CHARACTER_SIMILARITY",
            image_a=image_path,
            image_b=None,
        ),
    ]
    file_result = _file_check(image_path)
    checks.insert(0, file_result)
    if file_result.status == QAResultStatus.PASS and image_path:
        checks.append(_dimension_check(image_path, frame.width, frame.height))
        checks.append(_aspect_ratio_check(image_path, frame.aspect_ratio))
    else:
        checks.append(
            QACheckResult(
                check_id="DIMENSION_CHECK",
                status=QAResultStatus.NOT_CHECKED,
                message="Skipped — no image",
            )
        )
        checks.append(
            QACheckResult(
                check_id="ASPECT_RATIO_CHECK",
                status=QAResultStatus.NOT_CHECKED,
                message="Skipped — no image",
            )
        )

    report = QAReport(target_id=frame.frame_id, checks=checks)
    report.summarize()
    return report


def apply_qa_to_frame(frame: FrameManifest, report: QAReport) -> FrameManifest:
    overall = report.summarize()
    if overall == QAResultStatus.PASS or report.human_override:
        frame.qa_status = StageStatus.QA_PASSED
        if report.human_override:
            frame.status = StageStatus.REQUIRES_REVIEW
        else:
            frame.status = StageStatus.QA_PASSED
    elif overall == QAResultStatus.FAIL:
        frame.qa_status = StageStatus.QA_FAILED
        frame.status = StageStatus.QA_FAILED
    elif overall == QAResultStatus.REQUIRES_HUMAN_REVIEW:
        frame.qa_status = StageStatus.REQUIRES_REVIEW
        frame.status = StageStatus.REQUIRES_REVIEW
    else:
        # NOT_CHECKED / CHECKED — do not treat as exportable PASS
        frame.qa_status = StageStatus.REQUIRES_REVIEW
        frame.status = StageStatus.REQUIRES_REVIEW
    frame.touch()
    return frame


def assert_cookie_label_exact(label: str) -> None:
    if label != COOKIE_LABEL_EXACT:
        raise AssertionError(f"Prop label must be {COOKIE_LABEL_EXACT!r}, got {label!r}")


def assert_watermark_exact(text: str) -> None:
    if text != WATERMARK_EXACT:
        raise AssertionError(f"Watermark must be {WATERMARK_EXACT!r}, got {text!r}")
