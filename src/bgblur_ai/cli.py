"""Command line interface for the bgblur_ai SDK."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from bgblur_ai import DatasetProcessor, PrivacyBlur
from bgblur_ai.exceptions import PrivacyBlurError


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(prog="bgblur-ai", description="BGBlur API client")
    parser.add_argument("--api-key", default=os.getenv("BGBLUR_AI_API_KEY"), help="API key")
    parser.add_argument(
        "--base-url",
        default=os.getenv("BGBLUR_AI_BASE_URL", "https://www.bgblur.com"),
        help="API base URL",
    )
    parser.add_argument("--timeout", type=float, default=300.0, help="Per-request timeout in seconds")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Polling interval in seconds")
    parser.add_argument("--max-poll-time", type=float, default=1800.0, help="Maximum time to wait for a job")
    parser.add_argument("--max-retries", type=int, default=3, help="Maximum retry attempts")
    parser.add_argument("--quiet", action="store_true", help="Disable progress output")

    subparsers = parser.add_subparsers(dest="command", required=True)

    face_blur = subparsers.add_parser("face-blur", help="Blur faces in an image or video")
    face_blur.add_argument("input")
    face_blur.add_argument("output")
    face_blur.add_argument("--blur-type", default="gaussian")
    face_blur.set_defaults(handler=_run_face_blur)

    face_anonymize = subparsers.add_parser("face-anonymize", help="Anonymize faces in an image or video")
    face_anonymize.add_argument("input")
    face_anonymize.add_argument("output")
    face_anonymize.set_defaults(handler=_run_face_anonymize)

    plate = subparsers.add_parser("license-plate-blur", help="Blur license plates in an image or video")
    plate.add_argument("input")
    plate.add_argument("output")
    plate.set_defaults(handler=_run_license_plate_blur)

    anything = subparsers.add_parser("blur-anything", help="Blur objects matching a prompt")
    anything.add_argument("input")
    anything.add_argument("output")
    anything.add_argument("--prompt", required=True)
    anything.set_defaults(handler=_run_blur_anything)

    dataset = subparsers.add_parser("dataset-process", help="Process an image dataset for privacy-preserving training")
    dataset.add_argument("--input", required=True, dest="dataset_path")
    dataset.add_argument("--output", required=True, dest="output_path")
    dataset.add_argument("--face-blur", action="store_true")
    dataset.add_argument("--plate-blur", action="store_true")
    dataset.add_argument("--blur-anything", action="store_true")
    dataset.add_argument("--prompt")
    dataset.add_argument("--blur-type", default="gaussian")
    dataset.add_argument("--plate-mode", choices=("blur", "replace"), default="blur")
    dataset.add_argument("--replacement-image")
    dataset.add_argument("--max-workers", type=int)
    dataset.set_defaults(handler=_run_dataset_process)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the bgblur_ai CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.api_key:
        parser.error("An API key is required. Use --api-key or set BGBLUR_AI_API_KEY.")

    try:
        output_value = args.handler(args)
    except PrivacyBlurError as exc:
        print(f"bgblur-ai: {exc}", file=sys.stderr)
        return 1

    print(output_value)
    return 0


def _build_client(args: argparse.Namespace) -> PrivacyBlur:
    return PrivacyBlur(
        api_key=args.api_key,
        base_url=args.base_url,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
        max_poll_time=args.max_poll_time,
        max_retries=args.max_retries,
        progress=not args.quiet,
    )


def _run_face_blur(args: argparse.Namespace) -> Path:
    client = _build_client(args)
    try:
        return client.face_blur(input=args.input, output=args.output, blur_type=args.blur_type)
    finally:
        client.close()


def _run_face_anonymize(args: argparse.Namespace) -> Path:
    client = _build_client(args)
    try:
        return client.face_anonymize(input=args.input, output=args.output)
    finally:
        client.close()


def _run_license_plate_blur(args: argparse.Namespace) -> Path:
    client = _build_client(args)
    try:
        return client.license_plate_blur(input=args.input, output=args.output)
    finally:
        client.close()


def _run_blur_anything(args: argparse.Namespace) -> Path:
    client = _build_client(args)
    try:
        return client.blur_anything(input=args.input, output=args.output, prompt=args.prompt)
    finally:
        client.close()


def _run_dataset_process(args: argparse.Namespace) -> str:
    processor = DatasetProcessor(
        api_key=args.api_key,
        base_url=args.base_url,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
        max_poll_time=args.max_poll_time,
        max_retries=args.max_retries,
        show_progress=not args.quiet,
        max_workers=args.max_workers,
    )
    report = processor.process_dataset(
        dataset_path=args.dataset_path,
        output_path=args.output_path,
        face_blur=args.face_blur,
        plate_blur=args.plate_blur,
        blur_anything=args.blur_anything,
        prompt=args.prompt,
        blur_type=args.blur_type,
        plate_mode=args.plate_mode,
        replacement_image=args.replacement_image,
    )
    return report.to_json()
