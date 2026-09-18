"""capos.core package."""

from capos.core.schemas import COOKIE_LABEL_EXACT, WATERMARK_EXACT
from capos.core.status import FrameType, ProductionStage, StageStatus

__all__ = [
    "COOKIE_LABEL_EXACT",
    "WATERMARK_EXACT",
    "FrameType",
    "ProductionStage",
    "StageStatus",
]
