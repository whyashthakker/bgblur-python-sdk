"""Dataset scanning helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass(slots=True)
class ScanItem:
    """Represents a file found within a dataset tree."""

    source_path: Path
    relative_path: Path


@dataclass(slots=True)
class ScanResult:
    """Scanner output for images and non-image files."""

    images: list[ScanItem]
    passthrough_files: list[ScanItem]


class DatasetScanner:
    """Recursively scan a dataset directory for supported image files."""

    def scan(self, dataset_path: str | Path) -> ScanResult:
        """Scan the dataset and return supported images plus passthrough files."""
        root = Path(dataset_path).expanduser().resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"Dataset path not found: {root}")

        images: list[ScanItem] = []
        passthrough_files: list[ScanItem] = []

        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            item = ScanItem(source_path=path, relative_path=path.relative_to(root))
            if path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES:
                images.append(item)
            else:
                passthrough_files.append(item)

        return ScanResult(images=images, passthrough_files=passthrough_files)
