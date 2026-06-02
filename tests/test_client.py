from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from bgblur_ai import (
    AuthenticationError,
    InsufficientCreditsError,
    PrivacyBlur,
    PrivacyBlurError,
    RateLimitError,
    ServerError,
)


def _build_transport(
    *,
    media_kind: str = "image",
    operation: str = "face_blur",
    job_statuses: list[str] | None = None,
    download_content: bytes = b"processed",
) -> httpx.MockTransport:
    status_iter = iter(job_statuses or ["completed"])
    seen_upload_auth_headers: list[str | None] = []
    seen_download_auth_headers: list[str | None] = []
    seen_submitted_image_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == f"/api/v2/uploads/{media_kind}" and request.method == "POST":
            return httpx.Response(
                200,
                json={
                    "upload_url": "https://uploads.example.com/presigned",
                    "media_url": f"https://cdn.example.com/input.{ 'jpg' if media_kind == 'image' else 'mp4'}",
                },
            )
        if request.url.host == "uploads.example.com" and request.method == "PUT":
            seen_upload_auth_headers.append(request.headers.get("Authorization"))
            return httpx.Response(200, text="")
        if request.url.path == "/api/v2/images/face-blur" and request.method == "POST":
            submitted = json.loads(request.content)
            seen_submitted_image_urls.append(submitted["image_url"])
            return httpx.Response(200, json={"success": True, "status": "completed", "output_url": "https://files.example.com/output.jpg"})
        if request.url.path == "/api/v2/images/license-plate-blur" and request.method == "POST":
            return httpx.Response(200, json={"success": True, "status": "completed", "output_url": "https://files.example.com/output.jpg"})
        if request.url.path == "/api/v2/images/blur-anything" and request.method == "POST":
            return httpx.Response(200, json={"success": True, "status": "completed", "output_url": "https://files.example.com/output.jpg"})
        if request.url.path == "/api/v2/videos/face-blur" and request.method == "POST":
            return httpx.Response(200, json={"success": True, "status": "queued", "job_id": "job_123"})
        if request.url.path == "/api/v2/videos/license-plate-blur" and request.method == "POST":
            return httpx.Response(200, json={"success": True, "status": "queued", "job_id": "job_123"})
        if request.url.path == "/api/v2/videos/blur-anything" and request.method == "POST":
            return httpx.Response(200, json={"success": True, "status": "queued", "job_id": "job_123"})
        if request.url.path == "/api/v2/videos/face-anonymization" and request.method == "POST":
            return httpx.Response(200, json={"success": True, "status": "queued", "job_id": "job_123"})
        if request.url.path == "/api/v2/jobs/job_123":
            status = next(status_iter)
            if status == "failed":
                return httpx.Response(200, json={"success": True, "status": "failed", "message": "GPU failure"})
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "status": status,
                    "output_url": "https://files.example.com/download/result.bin",
                },
            )
        if request.url.host == "files.example.com":
            seen_download_auth_headers.append(request.headers.get("Authorization"))
            return httpx.Response(200, content=download_content)
        return httpx.Response(404, json={"message": "not found"})

    transport = httpx.MockTransport(handler)
    transport.seen_upload_auth_headers = seen_upload_auth_headers  # type: ignore[attr-defined]
    transport.seen_download_auth_headers = seen_download_auth_headers  # type: ignore[attr-defined]
    transport.seen_submitted_image_urls = seen_submitted_image_urls  # type: ignore[attr-defined]
    return transport


def test_face_blur_downloads_processed_file(tmp_path: Path) -> None:
    input_path = tmp_path / "input.jpg"
    output_path = tmp_path / "output.jpg"
    input_path.write_bytes(b"raw")

    transport = _build_transport(media_kind="image")
    client = PrivacyBlur(
        api_key="test-key",
        base_url="https://www.bgblur.com",
        poll_interval=0.0,
        http_client=httpx.Client(
            base_url="https://www.bgblur.com",
            transport=transport,
        ),
    )

    result = client.face_blur(input=input_path, output=output_path, blur_type="gaussian")

    assert result == output_path
    assert output_path.read_bytes() == b"processed"
    assert transport.seen_upload_auth_headers == [None]  # type: ignore[attr-defined]
    assert transport.seen_download_auth_headers == [None]  # type: ignore[attr-defined]
    assert transport.seen_submitted_image_urls == ["https://uploads.example.com/presigned"]  # type: ignore[attr-defined]


def test_blur_anything_requires_prompt(tmp_path: Path) -> None:
    input_path = tmp_path / "input.jpg"
    input_path.write_bytes(b"raw")
    client = PrivacyBlur(
        api_key="test-key",
        base_url="https://www.bgblur.com",
        http_client=httpx.Client(
            base_url="https://www.bgblur.com",
            transport=_build_transport(media_kind="image"),
        ),
    )

    with pytest.raises(ValueError, match="prompt must not be empty"):
        client.blur_anything(input=input_path, output=tmp_path / "out.jpg", prompt=" ")


def test_failed_job_raises_sdk_error(tmp_path: Path) -> None:
    input_path = tmp_path / "input.mp4"
    input_path.write_bytes(b"raw")
    client = PrivacyBlur(
        api_key="test-key",
        base_url="https://www.bgblur.com",
        poll_interval=0.0,
        http_client=httpx.Client(
            base_url="https://www.bgblur.com",
            transport=_build_transport(media_kind="video", operation="face_anonymize", job_statuses=["failed"]),
        ),
    )

    with pytest.raises(PrivacyBlurError, match="GPU failure"):
        client.face_anonymize(input=input_path, output=tmp_path / "output.jpg")


@pytest.mark.parametrize(
    ("status_code", "expected_exception"),
    [
        (401, AuthenticationError),
        (429, RateLimitError),
        (500, ServerError),
    ],
)
def test_http_errors_are_normalized(
    tmp_path: Path,
    status_code: int,
    expected_exception: type[Exception],
) -> None:
    input_path = tmp_path / "input.jpg"
    input_path.write_bytes(b"raw")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/uploads/image":
            return httpx.Response(status_code, json={"message": "boom"})
        return httpx.Response(404, json={"message": "not found"})

    client = PrivacyBlur(
        api_key="test-key",
        base_url="https://www.bgblur.com",
        http_client=httpx.Client(
            base_url="https://www.bgblur.com",
            transport=httpx.MockTransport(handler),
        ),
    )

    with pytest.raises(expected_exception):
        client.license_plate_blur(input=input_path, output=tmp_path / "output.jpg")


def test_insufficient_credits_error_has_pricing_url(tmp_path: Path) -> None:
    input_path = tmp_path / "input.jpg"
    input_path.write_bytes(b"raw")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/uploads/image":
            return httpx.Response(402, json={"error": {"code": "insufficient_credits", "message": "Not enough credits"}})
        return httpx.Response(404, json={"message": "not found"})

    client = PrivacyBlur(
        api_key="test-key",
        base_url="https://www.bgblur.com",
        http_client=httpx.Client(
            base_url="https://www.bgblur.com",
            transport=httpx.MockTransport(handler),
        ),
    )

    with pytest.raises(InsufficientCreditsError, match="https://www.bgblur.com/en/pricing"):
        client.license_plate_blur(input=input_path, output=tmp_path / "output.jpg")


def test_video_face_blur_polls_job_until_output_ready(tmp_path: Path) -> None:
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "output.mp4"
    input_path.write_bytes(b"raw")

    client = PrivacyBlur(
        api_key="test-key",
        base_url="https://www.bgblur.com",
        poll_interval=0.0,
        http_client=httpx.Client(
            base_url="https://www.bgblur.com",
            transport=_build_transport(media_kind="video", operation="face_blur", job_statuses=["queued", "processing", "completed"]),
        ),
    )

    result = client.face_blur(input=input_path, output=output_path, blur_type="pixelated")

    assert result == output_path
    assert output_path.read_bytes() == b"processed"
