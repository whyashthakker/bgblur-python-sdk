from __future__ import annotations

import json
from pathlib import Path

from privacyblur import cli


def test_cli_dataset_process_invokes_processor(monkeypatch, tmp_path: Path, capsys) -> None:
    dataset = tmp_path / "dataset"
    output = tmp_path / "dataset_private"
    dataset.mkdir()

    captured: dict[str, object] = {}

    class FakeReport:
        def to_json(self) -> str:
            return json.dumps({"images_processed": 1})

    class FakeProcessor:
        def __init__(self, **kwargs: object) -> None:
            captured["init"] = kwargs

        def process_dataset(self, **kwargs: object) -> FakeReport:
            captured["call"] = kwargs
            return FakeReport()

    monkeypatch.setattr(cli, "DatasetProcessor", FakeProcessor)

    exit_code = cli.main(
        [
            "--api-key",
            "test-key",
            "dataset-process",
            "--input",
            str(dataset),
            "--output",
            str(output),
            "--face-blur",
            "--plate-blur",
            "--blur-type",
            "pixelated",
        ]
    )

    stdout = capsys.readouterr().out.strip()

    assert exit_code == 0
    assert json.loads(stdout) == {"images_processed": 1}
    assert captured["call"] == {
        "dataset_path": str(dataset),
        "output_path": str(output),
        "face_blur": True,
        "plate_blur": True,
        "blur_anything": False,
        "prompt": None,
        "blur_type": "pixelated",
        "plate_mode": "blur",
        "replacement_image": None,
    }
