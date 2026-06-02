# bgblur-ai

Official Python SDK and CLI for [BGBlur.com](https://www.bgblur.com), an AI visual privacy platform for blurring and anonymizing faces, license plates, and custom objects in images and videos.

`bgblur-ai` is the Python SDK for BGBlur.com. Use it to add automated privacy protection, visual redaction, and dataset anonymization workflows to Python scripts, backend jobs, and command-line pipelines.

BGBlur.com helps creators, developers, businesses, and AI teams protect visual privacy in photos and videos. It is built for workflows where faces, license plates, people, vehicles, backgrounds, or sensitive objects need to be blurred before sharing, publishing, reviewing, or using media in datasets.


## Installation

```bash
pip install bgblur-ai
```

The PyPI package name is `bgblur-ai`. The Python import name is `bgblur_ai`.

## Authentication

Create an API key from your BGBlur developer dashboard:

```text
https://www.bgblur.com/developers/api-keys
```

Set it as an environment variable:

```bash
export BGBLUR_AI_API_KEY="YOUR_API_KEY"
```

Or pass it directly when creating a client.

## Quick Start

```python
from bgblur_ai import PrivacyBlur

with PrivacyBlur(api_key="YOUR_API_KEY") as client:
    client.face_blur(
        input="image.jpg",
        output="result.jpg",
        blur_type="gaussian",
    )
```

## Python Examples

Blur faces:

```python
from bgblur_ai import PrivacyBlur

with PrivacyBlur(api_key="YOUR_API_KEY") as client:
    client.face_blur(
        input="image.jpg",
        output="face-blurred.jpg",
        blur_type="gaussian",
    )
```

Blur license plates:

```python
from bgblur_ai import PrivacyBlur

with PrivacyBlur(api_key="YOUR_API_KEY") as client:
    client.license_plate_blur(
        input="car.jpg",
        output="plates-blurred.jpg",
    )
```

Blur anything with a prompt:

```python
from bgblur_ai import PrivacyBlur

with PrivacyBlur(api_key="YOUR_API_KEY") as client:
    client.blur_anything(
        input="street.jpg",
        prompt="person",
        output="objects-blurred.jpg",
    )
```

Anonymize faces in video:

```python
from bgblur_ai import PrivacyBlur

with PrivacyBlur(api_key="YOUR_API_KEY") as client:
    client.face_anonymize(
        input="interview.mp4",
        output="anonymous-video.mp4",
    )
```

## Dataset Processing

`DatasetProcessor` helps prepare privacy-safe image datasets by applying BGBlur operations across a folder.

```python
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

## CLI Usage

You can also run BGBlur from the command line.

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

## Errors

The SDK raises typed exceptions that can be caught in your application:

- `PrivacyBlurError`
- `AuthenticationError`
- `InsufficientCreditsError`
- `RateLimitError`
- `ServerError`

Example:

```python
from bgblur_ai import InsufficientCreditsError, PrivacyBlur, PrivacyBlurError

try:
    with PrivacyBlur(api_key="YOUR_API_KEY") as client:
        client.face_blur(input="image.jpg", output="result.jpg")
except InsufficientCreditsError as exc:
    print(exc)
except PrivacyBlurError as exc:
    print(f"BGBlur error: {exc}")
```

## What You Can Do

- Blur faces in images and videos for privacy protection.
- Anonymize faces in videos for identity protection.
- Blur license plates in vehicle images, dashcam footage, CCTV, and street scenes.
- Blur custom objects with a text prompt using BGBlur's blur-anything workflow.
- Prepare privacy-safe datasets for AI training, computer vision, and content review.
- Automate video redaction and image redaction from Python or the `bgblur-ai` CLI.

## Why BGBlur.com

BGBlur.com focuses on practical visual privacy automation. Manual video redaction and image editing can be slow, repetitive, and hard to scale. BGBlur helps teams process privacy-sensitive media faster by combining AI face blur, license plate blur, prompt-based object blur, and video anonymization in one platform.

Common use cases include:

- Privacy-safe social media publishing.
- CCTV, dashcam, bodycam, and street footage redaction.
- AI dataset anonymization before model training.
- Customer support, legal, security, and compliance media review.
- Creator, journalist, researcher, and business privacy workflows.

## Keywords

AI face blur, video anonymization, license plate blur, image redaction, video redaction, privacy SDK, Python SDK, dataset anonymization, blur anything, object blur, visual privacy automation.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest
```
