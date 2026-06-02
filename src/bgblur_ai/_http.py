"""Internal HTTP transport and response handling for bgblur_ai."""

from __future__ import annotations

import json
import mimetypes
import time
from pathlib import Path
from typing import Any

import httpx

from bgblur_ai.exceptions import (
    AuthenticationError,
    PrivacyBlurError,
    RateLimitError,
    ServerError,
)
from bgblur_ai.models import ClientConfig, UploadTarget
from bgblur_ai.progress import ProgressEvent, ProgressReporter


class APIClient:
    """Low-level API client with retries and error normalization."""

    def __init__(
        self,
        config: ClientConfig,
        progress: ProgressReporter,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._config = config
        self._progress = progress
        self._client = http_client or httpx.Client(
            base_url=config.base_url.rstrip("/"),
            timeout=config.timeout,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Accept": "application/json",
                "User-Agent": "bgblur-ai-python/0.1.0",
            },
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def create_upload_target(self, file_path: Path, media_kind: str) -> UploadTarget:
        """Create a presigned upload target for an image or video."""
        response = self.request(
            "POST",
            f"/api/v1/uploads/{media_kind}",
            json={
                "file_name": file_path.name,
                "file_type": _guess_content_type(file_path, media_kind),
                "file_size": file_path.stat().st_size,
            },
        )
        payload = self._json(response)
        upload_url = _extract_nested_value(payload, ("upload_url", "uploadUrl"))
        media_url = _extract_nested_value(payload, ("media_url", "image_url", "video_url"))
        if not upload_url or not media_url:
            raise PrivacyBlurError("Upload target response did not include upload_url and media_url.")
        return UploadTarget(
            upload_url=str(upload_url),
            media_url=str(media_url),
            media_kind=media_kind,
        )

    def upload_file(self, file_path: Path, target: UploadTarget) -> str:
        """Upload a local file to a presigned object-storage URL and return the media URL."""
        self._progress.emit(ProgressEvent(stage="upload", message=f"Uploading {file_path.name}"))
        with file_path.open("rb") as handle:
            response = self.request(
                "PUT",
                target.upload_url,
                content=handle.read(),
                headers={"Content-Type": _guess_content_type(file_path, target.media_kind)},
            )
        if response.status_code >= 400:
            self._raise_for_status(response)
        return target.media_url

    def submit_operation(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Submit a public API operation request and return the response payload."""
        response = self.request("POST", endpoint, json=payload)
        return self._json(response)

    def get_job(self, job_id: str) -> dict[str, Any]:
        """Fetch the latest job status payload."""
        response = self.request("GET", f"/api/v1/jobs/{job_id}")
        return self._json(response)

    def download_file(self, url: str, destination: Path) -> Path:
        """Download a processed file to the destination path."""
        self._progress.emit(ProgressEvent(stage="download", message=f"Saving to {destination}"))
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self._client.stream("GET", url) as response:
            self._raise_for_status(response)
            with destination.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)
        return destination

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Send an HTTP request with bounded retries for transient failures."""
        attempts = self._config.retry.max_attempts
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                response = self._client.request(method, url, **kwargs)
                if response.status_code in self._config.retry.retryable_status_codes and attempt < attempts:
                    self._progress.emit(
                        ProgressEvent(
                            stage="retry",
                            message=f"Retrying after HTTP {response.status_code} (attempt {attempt}/{attempts})",
                        )
                    )
                    time.sleep(self._config.retry.backoff_factor * attempt)
                    continue
                self._raise_for_status(response)
                return response
            except httpx.TimeoutException as exc:
                last_error = PrivacyBlurError(
                    f"Request timed out after {self._config.timeout} seconds."
                )
            except httpx.HTTPError as exc:
                last_error = PrivacyBlurError(f"HTTP request failed: {exc}")

            if attempt < attempts:
                self._progress.emit(
                    ProgressEvent(
                        stage="retry",
                        message=f"Retrying request (attempt {attempt}/{attempts})",
                    )
                )
                time.sleep(self._config.retry.backoff_factor * attempt)

        if last_error is not None:
            raise last_error
        raise PrivacyBlurError("Request failed without a captured error.")

    def _json(self, response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise PrivacyBlurError("API returned invalid JSON.") from exc

        if not isinstance(payload, dict):
            raise PrivacyBlurError("API returned an unexpected response payload.")
        return payload

    def _raise_for_status(self, response: httpx.Response) -> None:
        status_code = response.status_code
        if status_code < 400:
            return

        message = _extract_error_message(response)
        if status_code in (401, 403):
            raise AuthenticationError(message)
        if status_code == 429:
            raise RateLimitError(message)
        if status_code >= 500:
            raise ServerError(message)
        raise PrivacyBlurError(message)


def _extract_nested_value(payload: dict[str, Any], candidates: tuple[str, ...]) -> Any | None:
    for candidate in candidates:
        current: Any = payload
        found = True
        for part in candidate.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                found = False
                break
        if found and current not in (None, ""):
            return current
    return None


def _extract_error_message(response: httpx.Response) -> str:
    default = f"API request failed with status {response.status_code}."
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return response.text.strip() or default

    if isinstance(payload, dict):
        message = _extract_nested_value(payload, ("message", "error.message", "detail", "error"))
        if message:
            return str(message)
    return default


def _guess_content_type(file_path: Path, media_kind: str) -> str:
    guessed, _ = mimetypes.guess_type(file_path.name)
    if guessed:
        return guessed
    return "image/jpeg" if media_kind == "image" else "video/mp4"
