"""Reporting models for dataset processing."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(slots=True)
class DatasetProcessReport:
    """Summary of a dataset processing run."""

    images_processed: int
    faces_blurred: int
    license_plates_blurred: int
    objects_blurred: int
    errors: int
    processing_time_seconds: float

    def to_dict(self) -> dict[str, int | float | str]:
        """Return the report as a serializable dictionary."""
        payload = asdict(self)
        payload["processing_time_human"] = self.processing_time_human
        return payload

    @property
    def processing_time_human(self) -> str:
        """Return a human-readable duration string."""
        total_seconds = max(0, int(round(self.processing_time_seconds)))
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}h {minutes}m {seconds}s"
        return f"{minutes}m {seconds}s"

    def to_json(self, indent: int = 2) -> str:
        """Return the report as JSON."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_csv(self) -> str:
        """Return the report as a single-row CSV string."""
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=list(self.to_dict().keys()))
        writer.writeheader()
        writer.writerow(self.to_dict())
        return buffer.getvalue()

    def write_csv(self, path: str | Path) -> Path:
        """Write the report as CSV to disk."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(self.to_dict().keys()))
            writer.writeheader()
            writer.writerow(self.to_dict())
        return destination
