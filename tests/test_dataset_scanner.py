from __future__ import annotations

from pathlib import Path

from bgblur_ai.dataset.scanner import DatasetScanner


def test_dataset_scanner_finds_supported_images_and_passthrough_files(tmp_path: Path) -> None:
    (tmp_path / "train").mkdir()
    (tmp_path / "labels").mkdir()
    (tmp_path / "train" / "a.jpg").write_bytes(b"a")
    (tmp_path / "train" / "b.png").write_bytes(b"b")
    (tmp_path / "labels" / "a.txt").write_text("0 0.5 0.5 1 1", encoding="utf-8")

    result = DatasetScanner().scan(tmp_path)

    assert [item.relative_path.as_posix() for item in result.images] == ["train/a.jpg", "train/b.png"]
    assert [item.relative_path.as_posix() for item in result.passthrough_files] == ["labels/a.txt"]
