# bgblur-ai

`bgblur-ai` is a Python SDK and CLI for the BGBlur public API on `https://www.bgblur.com`. It does not run AI processing locally. Files are uploaded through BGBlur's presigned upload API, processing is delegated to the existing backend stack, and results are downloaded automatically.

## Installation

```bash
pip install bgblur-ai
```

## Quick start

```python
from bgblur_ai import PrivacyBlur

client = PrivacyBlur(api_key="YOUR_API_KEY")

client.face_blur(
    input="image.jpg",
    output="result.jpg",
    blur_type="gaussian",
)

client.face_anonymize(
    input="video.mp4",
    output="result.mp4",
)

client.license_plate_blur(
    input="car.jpg",
    output="result.jpg",
)

client.blur_anything(
    input="image.jpg",
    prompt="person",
    output="result.jpg",
)

from bgblur_ai import DatasetProcessor

processor = DatasetProcessor(api_key="YOUR_API_KEY")

report = processor.process_dataset(
    dataset_path="dataset",
    output_path="dataset_private",
    face_blur=True,
    plate_blur=True,
    blur_type="pixelated",
)

print(report.to_json())
```

## CLI

```bash
bgblur-ai face-blur input.jpg output.jpg --blur-type gaussian
bgblur-ai face-anonymize input.mp4 output.mp4
bgblur-ai license-plate-blur car.jpg result.jpg
bgblur-ai blur-anything image.jpg result.jpg --prompt "person"
bgblur-ai dataset-process --input dataset --output dataset_private --face-blur --plate-blur --blur-type pixelated
```

API key resolution order:

1. `--api-key`
2. `BGBLUR_AI_API_KEY`

Base URL resolution order:

1. `--base-url`
2. `BGBLUR_AI_BASE_URL`
3. `https://www.bgblur.com`

## API contract

The SDK follows the current BGBlur public API flow:

- `POST /api/v1/uploads/image` or `POST /api/v1/uploads/video` to obtain a presigned `upload_url` plus `image_url` or `video_url`
- `PUT` the original file bytes to the returned presigned upload URL
- `POST /api/v1/images/...` for synchronous image operations
- `POST /api/v1/videos/...` for async video operations
- `GET /api/v1/jobs/{job_id}` to inspect queued video jobs

The current implementation uses these BGBlur public endpoints:

- `POST /api/v1/images/face-blur`
- `POST /api/v1/images/license-plate-blur`
- `POST /api/v1/images/blur-anything`
- `POST /api/v1/videos/face-blur`
- `POST /api/v1/videos/license-plate-blur`
- `POST /api/v1/videos/blur-anything`
- `POST /api/v1/videos/face-anonymization`

`DatasetProcessor` uses those same public routes. `plate_mode="replace"` is not currently exposed by the BGBlur public API, so the SDK raises a clear error for that mode instead of silently falling back to local processing.

## Errors

The SDK raises:

- `PrivacyBlurError`
- `AuthenticationError`
- `RateLimitError`
- `ServerError`

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest
```
