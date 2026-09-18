"""Reusable deterministic text component masters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from capos.composition.text import apply_speech_bubble, apply_watermark, compose_cover_title
from capos.core.schemas import COOKIE_LABEL_EXACT, WATERMARK_EXACT
from capos.qa.validators import assert_cookie_label_exact, assert_watermark_exact


@dataclass(frozen=True)
class SpeechBubbleMaster:
    fill: str = "cream/off-white"
    outline: str = "bold dark"
    lettering: str = "bold black uppercase"
    avoid: tuple[str, ...] = ("faces", "important gestures", "story props")

    def render(
        self,
        image_path: Path,
        output_path: Path,
        *,
        dialogue: str,
        box: tuple[int, int, int, int] | None = None,
    ) -> str:
        """Composite exact approved dialogue — never paraphrase."""
        return apply_speech_bubble(image_path, output_path, dialogue=dialogue, box=box)


@dataclass(frozen=True)
class PropLabelMaster:
    label: str = COOKIE_LABEL_EXACT

    def exact(self) -> str:
        assert_cookie_label_exact(self.label)
        return self.label


@dataclass(frozen=True)
class WatermarkMaster:
    text: str = WATERMARK_EXACT

    def apply(self, image_path: Path, output_path: Path) -> str:
        assert_watermark_exact(self.text)
        return apply_watermark(image_path, output_path, text=self.text)


@dataclass(frozen=True)
class CoverTitleMaster:
    def apply(
        self,
        image_path: Path,
        output_path: Path,
        *,
        series_title: str,
        season_episode: str,
        episode_title: str,
    ) -> Path:
        return compose_cover_title(
            image_path,
            output_path,
            series_title=series_title,
            season_episode=season_episode,
            episode_title=episode_title,
        )


SPEECH_BUBBLE = SpeechBubbleMaster()
PROP_LABEL_COOKIES = PropLabelMaster(label=COOKIE_LABEL_EXACT)
WATERMARK = WatermarkMaster(text=WATERMARK_EXACT)
COVER_TITLE = CoverTitleMaster()
