"""Dataset processor built on top of the PrivacyBlur SDK."""

from __future__ import annotations

import logging
import shutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from tqdm import tqdm

from privacyblur.client import PrivacyBlur
from privacyblur.dataset.report import DatasetProcessReport
from privacyblur.dataset.scanner import DatasetScanner, ScanItem
from privacyblur.exceptions import PrivacyBlurError


ClientFactory = Callable[..., PrivacyBlur]


@dataclass(slots=True)
class _ImageProcessResult:
    success: bool
    faces_blurred: int
    license_plates_blurred: int
    objects_blurred: int


class DatasetProcessor:
    """Process image datasets through the PrivacyBlur backend without local AI inference."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://www.bgblur.com",
        timeout: float = 300.0,
        poll_interval: float = 2.0,
        max_poll_time: float = 1800.0,
        max_retries: int = 3,
        max_workers: int | None = None,
        show_progress: bool = True,
        logger: logging.Logger | None = None,
        client_factory: ClientFactory | None = None,
    ) -> None:
        """Create a dataset processor using the existing PrivacyBlur SDK."""
        self._client_kwargs = {
            "api_key": api_key,
            "base_url": base_url,
            "timeout": timeout,
            "poll_interval": poll_interval,
            "max_poll_time": max_poll_time,
            "max_retries": max_retries,
            "progress": False,
        }
        self._max_workers = max_workers
        self._show_progress = show_progress
        self._logger = logger or logging.getLogger("privacyblur.dataset")
        self._scanner = DatasetScanner()
        self._client_factory = client_factory or PrivacyBlur

    def process_dataset(
        self,
        *,
        dataset_path: str | Path,
        output_path: str | Path,
        face_blur: bool = False,
        plate_blur: bool = False,
        blur_anything: bool = False,
        prompt: str | None = None,
        blur_type: str = "gaussian",
        plate_mode: str = "blur",
        replacement_image: str | Path | None = None,
    ) -> DatasetProcessReport:
        """Process all supported dataset images and preserve folder structure."""
        self._validate_options(
            face_blur=face_blur,
            plate_blur=plate_blur,
            blur_anything=blur_anything,
            prompt=prompt,
            plate_mode=plate_mode,
            replacement_image=replacement_image,
        )

        dataset_root = Path(dataset_path).expanduser().resolve()
        output_root = Path(output_path).expanduser().resolve()
        scan_result = self._scanner.scan(dataset_root)
        output_root.mkdir(parents=True, exist_ok=True)

        self._copy_passthrough_files(scan_result.passthrough_files, output_root)
        self._logger.info(
            "dataset_processing_started",
            extra={
                "dataset_path": str(dataset_root),
                "output_path": str(output_root),
                "images": len(scan_result.images),
            },
        )

        start = time.monotonic()
        images_processed = 0
        faces_blurred = 0
        license_plates_blurred = 0
        objects_blurred = 0
        errors = 0

        worker_count = self._resolve_worker_count(len(scan_result.images))
        progress_bar = tqdm(
            total=len(scan_result.images),
            desc="Processing dataset",
            unit="image",
            disable=not self._show_progress,
        )

        try:
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = [
                    executor.submit(
                        self._process_image,
                        item,
                        dataset_root,
                        output_root,
                        face_blur,
                        plate_blur,
                        blur_anything,
                        prompt,
                        blur_type,
                        plate_mode,
                        replacement_image,
                    )
                    for item in scan_result.images
                ]

                for future in as_completed(futures):
                    progress_bar.update(1)
                    try:
                        result = future.result()
                    except Exception:
                        errors += 1
                        self._logger.exception("dataset_image_failed")
                        continue

                    if result.success:
                        images_processed += 1
                        faces_blurred += result.faces_blurred
                        license_plates_blurred += result.license_plates_blurred
                        objects_blurred += result.objects_blurred
                    else:
                        errors += 1
        finally:
            progress_bar.close()

        report = DatasetProcessReport(
            images_processed=images_processed,
            faces_blurred=faces_blurred,
            license_plates_blurred=license_plates_blurred,
            objects_blurred=objects_blurred,
            errors=errors,
            processing_time_seconds=time.monotonic() - start,
        )

        self._logger.info("dataset_processing_finished", extra=report.to_dict())
        return report

    def _process_image(
        self,
        item: ScanItem,
        dataset_root: Path,
        output_root: Path,
        face_blur: bool,
        plate_blur: bool,
        blur_anything: bool,
        prompt: str | None,
        blur_type: str,
        plate_mode: str,
        replacement_image: str | Path | None,
    ) -> _ImageProcessResult:
        destination = output_root / item.relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)

        client = self._client_factory(**self._client_kwargs)
        try:
            metrics = {"faces_blurred": 0, "license_plates_blurred": 0, "objects_blurred": 0}
            current_input = item.source_path

            with tempfile.TemporaryDirectory(prefix="privacyblur-dataset-") as temp_dir:
                temp_root = Path(temp_dir)

                if face_blur:
                    next_output = temp_root / f"{item.source_path.stem}.face{item.source_path.suffix}"
                    client.face_blur(input=current_input, output=next_output, blur_type=blur_type)
                    current_input = next_output
                    metrics["faces_blurred"] += 1

                if plate_blur:
                    next_output = temp_root / f"{item.source_path.stem}.plate{item.source_path.suffix}"
                    client.license_plate_blur(input=current_input, output=next_output)
                    current_input = next_output
                    metrics["license_plates_blurred"] += 1

                if blur_anything and prompt is not None:
                    next_output = temp_root / f"{item.source_path.stem}.prompt{item.source_path.suffix}"
                    client.blur_anything(input=current_input, output=next_output, prompt=prompt)
                    current_input = next_output
                    metrics["objects_blurred"] += 1

                shutil.copy2(current_input, destination)

            self._logger.info(
                "dataset_image_processed",
                extra={
                    "source_path": str(item.source_path),
                    "output_path": str(destination),
                    **metrics,
                },
            )
            return _ImageProcessResult(success=True, **metrics)
        finally:
            client.close()

    def _copy_passthrough_files(self, items: list[ScanItem], output_root: Path) -> None:
        for item in items:
            destination = output_root / item.relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item.source_path, destination)

    def _resolve_worker_count(self, image_count: int) -> int:
        if image_count <= 1:
            return 1
        if self._max_workers is not None:
            return max(1, self._max_workers)
        return min(32, image_count)

    def _validate_options(
        self,
        *,
        face_blur: bool,
        plate_blur: bool,
        blur_anything: bool,
        prompt: str | None,
        plate_mode: str,
        replacement_image: str | Path | None,
    ) -> None:
        if not any((face_blur, plate_blur, blur_anything)):
            raise ValueError("At least one dataset privacy operation must be enabled.")
        if blur_anything and not (prompt and prompt.strip()):
            raise ValueError("prompt is required when blur_anything is enabled.")
        if plate_mode not in {"blur", "replace"}:
            raise ValueError("plate_mode must be either 'blur' or 'replace'.")
        if plate_mode == "replace" and not plate_blur:
            raise ValueError("plate_mode='replace' requires plate_blur=True.")
        if plate_mode == "replace" and replacement_image is None:
            raise ValueError("replacement_image is required when plate_mode='replace'.")
        if plate_mode == "replace":
            raise PrivacyBlurError(
                "plate_mode='replace' is not exposed by the current public BGBlur API. "
                "The public SDK can only use the routes available on https://www.bgblur.com/api/v1."
            )
