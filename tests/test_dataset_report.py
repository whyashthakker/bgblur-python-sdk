from __future__ import annotations

from bgblur_ai.dataset.report import DatasetProcessReport


def test_dataset_report_to_json_contains_human_duration() -> None:
    report = DatasetProcessReport(
        images_processed=10,
        faces_blurred=4,
        license_plates_blurred=2,
        objects_blurred=1,
        errors=0,
        processing_time_seconds=125,
    )

    payload = report.to_json()

    assert '"processing_time_human": "2m 5s"' in payload


def test_dataset_report_to_csv_contains_headers() -> None:
    report = DatasetProcessReport(
        images_processed=1,
        faces_blurred=1,
        license_plates_blurred=0,
        objects_blurred=0,
        errors=0,
        processing_time_seconds=5,
    )

    payload = report.to_csv()

    assert "images_processed" in payload
    assert "processing_time_human" in payload
