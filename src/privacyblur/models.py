"""Shared type models used by the privacyblur SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class RetryConfig:
    """Retry behavior for transient HTTP failures."""

    max_attempts: int = 3
    backoff_factor: float = 0.5
    retryable_status_codes: tuple[int, ...] = (408, 429, 500, 502, 503, 504)


@dataclass(slots=True)
class ClientConfig:
    """Configuration for the PrivacyBlur client."""

    api_key: str
    base_url: str = "https://www.bgblur.com"
    timeout: float = 300.0
    poll_interval: float = 2.0
    max_poll_time: float = 1800.0
    retry: RetryConfig = field(default_factory=RetryConfig)


@dataclass(slots=True)
class JobResult:
    """Represents a completed remote processing job."""

    job_id: str
    status: str
    download_url: str
    raw_response: dict[str, Any]


@dataclass(slots=True)
class UploadTarget:
    """Represents a presigned upload target returned by the public API."""

    upload_url: str
    media_url: str
    media_kind: str


PathLike = str | Path
