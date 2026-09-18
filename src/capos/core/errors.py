"""Shared errors."""

from __future__ import annotations


class CaposError(Exception):
    """Base CAPOS error."""

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint

    def __str__(self) -> str:
        base = super().__str__()
        if self.hint:
            return f"{base} (hint: {self.hint})"
        return base


class ValidationError(CaposError):
    """Invalid state or input."""


class ContinuityError(CaposError):
    """Continuity QA or inheritance failure."""


class ExportBlockedError(CaposError):
    """Export refused because QA/gates failed."""


class BackendUnavailable(CaposError):
    """Generation backend not available."""


class NotCheckedError(CaposError):
    """Raised when a check cannot be performed honestly."""
