"""Public client for the privacyblur SDK."""

from __future__ import annotations

import time
from pathlib import Path
from pathlib import Path
from typing import Any

import httpx

from privacyblur._http import APIClient, _extract_nested_value
from privacyblur.exceptions import PrivacyBlurError
from privacyblur.models import ClientConfig, JobResult, PathLike, RetryConfig
from privacyblur.progress import (
    NullProgressReporter,
    ProgressEvent,
    ProgressReporter,
    StdoutProgressReporter,
)


class PrivacyBlur:
    """Synchronous SDK client for the PrivacyBlur/BGBlur API."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://www.bgblur.com",
        timeout: float = 300.0,
        poll_interval: float = 2.0,
        max_poll_time: float = 1800.0,
        max_retries: int = 3,
        progress: bool = False,
        progress_reporter: ProgressReporter | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        """
        Create a new SDK client.

        Args:
            api_key: Bearer token used to authenticate requests.
            base_url: Base URL for the PrivacyBlur API.
            timeout: Per-request timeout in seconds.
            poll_interval: Seconds between job status polls.
            max_poll_time: Maximum total wait time for a job.
            max_retries: Number of retry attempts for transient HTTP failures.
            progress: If True, emit simple stdout progress messages.
            progress_reporter: Custom progress reporter implementation.
            http_client: Optional injected ``httpx.Client`` for testing or advanced use.
        """
        if not api_key.strip():
            raise ValueError("api_key must not be empty.")

        reporter = progress_reporter
        if reporter is None:
            reporter = StdoutProgressReporter() if progress else NullProgressReporter()

        self._config = ClientConfig(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            poll_interval=poll_interval,
            max_poll_time=max_poll_time,
            retry=RetryConfig(max_attempts=max_retries),
        )
        self._progress = reporter
        self._api = APIClient(self._config, progress=reporter, http_client=http_client)

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._api.close()

    def __enter__(self) -> "PrivacyBlur":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def face_blur(self, *, input: PathLike, output: PathLike, blur_type: str = "gaussian") -> Path:
        """Blur faces in an image or video."""
        return self._process(
            operation="face_blur",
            input=input,
            output=output,
            options={"blur_type": blur_type},
        )

    def face_anonymize(self, *, input: PathLike, output: PathLike) -> Path:
        """Anonymize faces in an image or video."""
        return self._process(
            operation="face_anonymize",
            input=input,
            output=output,
            options={},
        )

    def license_plate_blur(self, *, input: PathLike, output: PathLike) -> Path:
        """Blur detected license plates in an image or video."""
        return self._process(
            operation="license_plate_blur",
            input=input,
            output=output,
            options={},
        )

    def blur_anything(self, *, input: PathLike, prompt: str, output: PathLike) -> Path:
        """Blur objects matching a text prompt."""
        if not prompt.strip():
            raise ValueError("prompt must not be empty.")

        return self._process(
            operation="blur_anything",
            input=input,
            output=output,
            options={"prompt": prompt},
        )

    def _process(self, *, operation: str, input: PathLike, output: PathLike, options: dict[str, Any]) -> Path:
        input_path = Path(input).expanduser().resolve()
        output_path = Path(output).expanduser()

        if not input_path.is_file():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        media_kind = _detect_media_kind(input_path)
        if operation == "face_anonymize" and media_kind != "video":
            raise PrivacyBlurError("face_anonymize is only supported for videos in the current BGBlur API.")

        upload_target = self._api.create_upload_target(input_path, media_kind)
        media_url = self._api.upload_file(input_path, upload_target)
        payload = self._submit_public_operation(operation=operation, media_kind=media_kind, media_url=media_url, options=options)

        status = str(_extract_nested_value(payload, ("status",)) or "").lower()
        output_url = _extract_nested_value(payload, ("output_url", "result.output_url", "result.file_url", "file_url", "url"))
        job_id = _extract_nested_value(payload, ("job_id", "jobId", "id", "batch_request_id"))

        if output_url:
            return self._api.download_file(str(output_url), output_path)

        if job_id and status in {"queued", "processing", "pending", "unknown"}:
            result = self._wait_for_job(str(job_id))
            return self._api.download_file(result.download_url, output_path)

        raise PrivacyBlurError("Operation did not return an output URL or a pollable job ID.")

    def _submit_public_operation(
        self,
        *,
        operation: str,
        media_kind: str,
        media_url: str,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        endpoint, payload = _build_public_api_request(
            operation=operation,
            media_kind=media_kind,
            media_url=media_url,
            options=options,
        )
        self._progress.emit(ProgressEvent(stage="submit", message=f"Submitting {operation} request"))
        return self._api.submit_operation(endpoint, payload)

    def _wait_for_job(self, job_id: str) -> JobResult:
        start = time.monotonic()

        while True:
            payload = self._api.get_job(job_id)
            status = str(_extract_nested_value(payload, ("status", "job.status")) or "").lower()
            self._progress.emit(ProgressEvent(stage="process", message=f"Job {job_id} status: {status or 'unknown'}"))

            if status in {"completed", "succeeded", "success"}:
                download_url = _extract_nested_value(
                    payload,
                    (
                        "output_url",
                        "download_url",
                        "result.output_url",
                        "result.file_url",
                        "result.url",
                        "output.url",
                    ),
                )
                if not download_url:
                    raise PrivacyBlurError("Completed job response did not include a download URL.")
                return JobResult(
                    job_id=job_id,
                    status=status,
                    download_url=str(download_url),
                    raw_response=payload,
                )

            if status in {"failed", "error", "cancelled", "canceled"}:
                message = _extract_nested_value(payload, ("message", "error", "detail", "result.error"))
                raise PrivacyBlurError(f"Remote job failed: {message or 'unknown error'}")

            elapsed = time.monotonic() - start
            if elapsed > self._config.max_poll_time:
                raise PrivacyBlurError(
                    f"Timed out waiting for job {job_id} after {self._config.max_poll_time} seconds."
                )

            time.sleep(self._config.poll_interval)


def _detect_media_kind(input_path: Path) -> str:
    image_suffixes = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
    video_suffixes = {".mp4", ".mov", ".webm", ".mkv", ".avi"}
    suffix = input_path.suffix.lower()
    if suffix in image_suffixes:
        return "image"
    if suffix in video_suffixes:
        return "video"
    raise PrivacyBlurError(f"Unsupported media type for file: {input_path.name}")


def _build_public_api_request(
    *,
    operation: str,
    media_kind: str,
    media_url: str,
    options: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    pixelated = options.get("blur_type") == "pixelated"
    blur_strength = 0.7

    if media_kind == "image":
        if operation == "face_blur":
            return (
                "/api/v1/images/face-blur",
                {
                    "image_url": media_url,
                    "blur_strength": blur_strength,
                    "pixelated": pixelated,
                },
            )
        if operation == "license_plate_blur":
            return (
                "/api/v1/images/license-plate-blur",
                {
                    "image_url": media_url,
                    "blur_strength": blur_strength,
                    "pixelated": pixelated,
                },
            )
        if operation == "blur_anything":
            return (
                "/api/v1/images/blur-anything",
                {
                    "image_url": media_url,
                    "prompt": options["prompt"],
                    "blur_strength": blur_strength,
                    "pixelated": pixelated,
                },
            )
        raise PrivacyBlurError(f"Unsupported image operation: {operation}")

    if operation == "face_blur":
        return (
            "/api/v1/videos/face-blur",
            {
                "video_url": media_url,
                "blur_strength": blur_strength,
                "pixelated": pixelated,
            },
        )
    if operation == "license_plate_blur":
        return (
            "/api/v1/videos/license-plate-blur",
            {
                "video_url": media_url,
                "blur_strength": blur_strength,
                "pixelated": pixelated,
            },
        )
    if operation == "blur_anything":
        return (
            "/api/v1/videos/blur-anything",
            {
                "video_url": media_url,
                "prompt": options["prompt"],
                "blur_strength": blur_strength,
                "pixelated": pixelated,
            },
        )
    if operation == "face_anonymize":
        return (
            "/api/v1/videos/face-anonymization",
            {
                "video_url": media_url,
            },
        )
    raise PrivacyBlurError(f"Unsupported video operation: {operation}")
