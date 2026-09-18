"""Provider-neutral audio interfaces + subtitle generation from approved script."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from capos.core.schemas import DialogueLine, ScriptDocument


class AudioClip(BaseModel):
    clip_id: str
    kind: str  # voice | music | sfx
    path: str | None = None
    license: str = "UNSPECIFIED"
    provenance: str = ""
    replaceable: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class AudioBackend(ABC):
    name: str = "base"

    @abstractmethod
    def available(self) -> tuple[bool, str]: ...

    @abstractmethod
    def synthesize_voice(self, *, text: str, speaker: str, output_path: Path) -> AudioClip: ...


class NullAudioBackend(AudioBackend):
    name = "null"

    def available(self) -> tuple[bool, str]:
        return False, "No audio provider configured"

    def synthesize_voice(self, *, text: str, speaker: str, output_path: Path) -> AudioClip:
        raise RuntimeError("NullAudioBackend cannot synthesize voice")


class SubtitleCue(BaseModel):
    index: int
    start_ms: int
    end_ms: int
    text: str
    speaker: str = ""


def cues_from_script(
    script: ScriptDocument,
    *,
    ms_per_line: int = 2000,
    gap_ms: int = 200,
) -> list[SubtitleCue]:
    """Subtitles come from approved script dialogue — never OCR."""
    cues: list[SubtitleCue] = []
    t = 0
    for i, line in enumerate(script.lines, start=1):
        start = t
        end = t + ms_per_line
        cues.append(
            SubtitleCue(
                index=i,
                start_ms=start,
                end_ms=end,
                text=line.text,
                speaker=line.speaker,
            )
        )
        t = end + gap_ms
    return cues


def _fmt_ts(ms: int) -> str:
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    s = ms // 1000
    milli = ms % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{milli:03d}"


def _fmt_vtt(ms: int) -> str:
    return _fmt_ts(ms).replace(",", ".")


def write_srt(cues: list[SubtitleCue], path: Path) -> Path:
    lines: list[str] = []
    for c in cues:
        lines.append(str(c.index))
        lines.append(f"{_fmt_ts(c.start_ms)} --> {_fmt_ts(c.end_ms)}")
        lines.append(c.text)
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_vtt(cues: list[SubtitleCue], path: Path) -> Path:
    lines = ["WEBVTT", ""]
    for c in cues:
        lines.append(f"{_fmt_vtt(c.start_ms)} --> {_fmt_vtt(c.end_ms)}")
        lines.append(c.text)
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def locked_dialogue_texts(lines: list[DialogueLine]) -> list[str]:
    return [ln.text for ln in lines if ln.locked]
