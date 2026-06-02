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
        self._owns_client = http_client is None
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
        if self._owns_client:
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
            upload_object_url=str(upload_url).split("?", 1)[0],
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
                include_auth=False,
            )
        if response.status_code >= 400:
            self._raise_for_status(response)
        return target.upload_object_url or target.media_url

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
        response = self.request("GET", url, stream=True, include_auth=False)
        try:
            self._raise_for_status(response)
            with destination.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)
        finally:
            response.close()
        return destination

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Send an HTTP request with bounded retries for transient failures."""
        include_auth = kwargs.pop("include_auth", True)
        stream = kwargs.pop("stream", False)
        attempts = self._config.retry.max_attempts
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                request_kwargs = kwargs.copy()
                request_headers = dict(request_kwargs.pop("headers", {}) or {})
                if request_headers:
                    request_kwargs["headers"] = request_headers

                request = self._client.build_request(method, url, **request_kwargs)
                if not include_auth and "Authorization" in request.headers:
                    del request.headers["Authorization"]

                if stream:
                    response = self._client.send(request, stream=True)
                else:
                    response = self._client.send(request)
                if response.status_code in self._config.retry.retryable_status_codes and attempt < attempts:
                    if stream:
                        response.close()
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
    request = response.request
    parts = [
        f"API request failed with status {response.status_code}",
        f"{request.method} {response.url}",
    ]

    request_id = _extract_request_id(response)
    if request_id:
        parts.append(f"request_id={request_id}")

    try:
        payload = response.json()
    except json.JSONDecodeError:
        body = response.text.strip()
        if body:
            parts.append(f"body={body[:1000]}")
        return "; ".join(parts) + "."

    if isinstance(payload, dict):
        message = _extract_nested_value(
            payload,
            (
                "message",
                "error.message",
                "error_description",
                "detail",
                "error",
                "code",
            ),
        )
        if message:
            parts.append(f"message={message}")
        error_code = _extract_nested_value(payload, ("error.code", "code"))
        if error_code and str(error_code) != str(message):
            parts.append(f"code={error_code}")
        parts.append(f"response={json.dumps(payload, separators=(',', ':'))[:1000]}")
        return "; ".join(parts) + "."

    parts.append(f"response={payload!r}")
    return "; ".join(parts) + "."


def _extract_request_id(response: httpx.Response) -> str | None:
    for header in (
        "x-request-id",
        "x-vercel-id",
        "cf-ray",
        "x-amz-request-id",
        "x-amz-id-2",
    ):
        value = response.headers.get(header)
        if value:
            return value
    return None


def _guess_content_type(file_path: Path, media_kind: str) -> str:
    guessed, _ = mimetypes.guess_type(file_path.name)
    if guessed:
        return guessed
    return "image/jpeg" if media_kind == "image" else "video/mp4"
