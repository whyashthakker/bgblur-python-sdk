from __future__ import annotations

from pathlib import Path

import pytest

from privacyblur import DatasetProcessor


class _FakeClient:
    instances: list["_FakeClient"] = []

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.closed = False
        _FakeClient.instances.append(self)

    def face_blur(self, *, input: Path, output: Path, blur_type: str) -> Path:
        self.calls.append(("face_blur", {"input": input, "output": output, "blur_type": blur_type}))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"processed:face_blur")
        return output

    def license_plate_blur(self, *, input: Path, output: Path) -> Path:
        self.calls.append(("license_plate_blur", {"input": input, "output": output}))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"processed:license_plate_blur")
        return output

    def blur_anything(self, *, input: Path, output: Path, prompt: str) -> Path:
        self.calls.append(("blur_anything", {"input": input, "output": output, "prompt": prompt}))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"processed:blur_anything")
        return output

    def close(self) -> None:
        self.closed = True


def test_dataset_processor_processes_images_and_copies_passthrough_files(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    output = tmp_path / "dataset_private"
    (dataset / "train").mkdir(parents=True)
    (dataset / "labels").mkdir()
    (dataset / "train" / "a.jpg").write_bytes(b"a")
    (dataset / "labels" / "a.txt").write_text("label", encoding="utf-8")

    _FakeClient.instances.clear()
    processor = DatasetProcessor(
        api_key="test-key",
        show_progress=False,
        max_workers=1,
        client_factory=_FakeClient,
    )

    report = processor.process_dataset(
        dataset_path=dataset,
        output_path=output,
        face_blur=True,
        plate_blur=True,
        blur_anything=True,
        prompt="person",
        blur_type="pixelated",
    )

    assert report.images_processed == 1
    assert report.faces_blurred == 1
    assert report.license_plates_blurred == 1
    assert report.objects_blurred == 1
    assert report.errors == 0
    assert (output / "train" / "a.jpg").read_bytes() == b"processed:blur_anything"
    assert (output / "labels" / "a.txt").read_text(encoding="utf-8") == "label"

    worker_client = _FakeClient.instances[0]
    assert [call[0] for call in worker_client.calls] == [
        "face_blur",
        "license_plate_blur",
        "blur_anything",
    ]


def test_dataset_processor_uploads_replacement_plate_image_once(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    output = tmp_path / "dataset_private"
    replacement = tmp_path / "blank_plate.png"
    (dataset / "images").mkdir(parents=True)
    (dataset / "images" / "car.jpg").write_bytes(b"a")
    replacement.write_bytes(b"plate")

    _FakeClient.instances.clear()
    processor = DatasetProcessor(
        api_key="test-key",
        show_progress=False,
        max_workers=1,
        client_factory=_FakeClient,
    )

    with pytest.raises(Exception, match="not exposed by the current public BGBlur API"):
        processor.process_dataset(
            dataset_path=dataset,
            output_path=output,
            plate_blur=True,
            plate_mode="replace",
            replacement_image=replacement,
        )


def test_dataset_processor_requires_prompt_for_blur_anything(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    output = tmp_path / "dataset_private"
    (dataset / "images").mkdir(parents=True)
    (dataset / "images" / "sample.jpg").write_bytes(b"a")

    processor = DatasetProcessor(api_key="test-key", show_progress=False, client_factory=_FakeClient)

    with pytest.raises(ValueError, match="prompt is required"):
        processor.process_dataset(
            dataset_path=dataset,
            output_path=output,
            blur_anything=True,
        )
