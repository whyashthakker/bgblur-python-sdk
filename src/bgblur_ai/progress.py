"""Progress reporting utilities for the bgblur_ai SDK."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ProgressEvent:
    """Describes a high-level progress event emitted by the SDK."""

    stage: str
    message: str


class ProgressReporter:
    """Interface for receiving SDK progress events."""

    def emit(self, event: ProgressEvent) -> None:
        """Handle a progress event."""


class NullProgressReporter(ProgressReporter):
    """Progress reporter that ignores all events."""

    def emit(self, event: ProgressEvent) -> None:
        return None


class StdoutProgressReporter(ProgressReporter):
    """Simple text progress reporter for CLI and interactive use."""

    def emit(self, event: ProgressEvent) -> None:
        print(f"[bgblur-ai] {event.stage}: {event.message}")
