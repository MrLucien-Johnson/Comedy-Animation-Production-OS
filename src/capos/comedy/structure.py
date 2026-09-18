"""Comedy structure + light engagement checks."""

from __future__ import annotations

from capos.core.schemas import StoryboardBeat
from capos.core.status import ComedyBeat

DEFAULT_ARC: tuple[ComedyBeat, ...] = (
    ComedyBeat.SETUP,
    ComedyBeat.TEMPTATION,
    ComedyBeat.ESCALATION,
    ComedyBeat.DISCOVERY,
    ComedyBeat.REACTION,
    ComedyBeat.PUNCHLINE,
)

CATCHPHRASE = "MI NEVA DO NUTTN!"


def validate_comedy_arc(beats: list[ComedyBeat]) -> list[str]:
    """Return warnings (not hard errors) for missing structural beats."""
    warnings: list[str] = []
    present = set(beats)
    for required in (ComedyBeat.SETUP, ComedyBeat.PUNCHLINE):
        if required not in present:
            warnings.append(f"Missing comedy beat: {required.value}")
    if ComedyBeat.TEMPTATION not in present and ComedyBeat.MISUNDERSTANDING not in present:
        warnings.append("Missing TEMPTATION or MISUNDERSTANDING beat")
    return warnings


def engagement_notes(beats: list[StoryboardBeat]) -> list[str]:
    notes: list[str] = []
    if not beats:
        return ["No storyboard beats — cannot evaluate engagement"]
    notes.append("Check strong opening image on first beat")
    notes.append("Ensure clear visual premise within first two beats")
    if not any(b.comedy_beat == ComedyBeat.REACTION for b in beats):
        notes.append("Consider adding a reaction shot")
    if not any(b.comedy_beat == ComedyBeat.PUNCHLINE for b in beats):
        notes.append("Missing strong final beat / punchline")
    return notes


def maybe_include_catchphrase(include: bool) -> str | None:
    """Do not force catchphrase when it damages the joke."""
    return CATCHPHRASE if include else None
