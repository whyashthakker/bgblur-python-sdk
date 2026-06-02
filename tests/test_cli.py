from __future__ import annotations

from pathlib import Path

from privacyblur import cli


def test_cli_face_blur_invokes_client(monkeypatch, tmp_path: Path, capsys) -> None:
    input_path = tmp_path / "input.jpg"
    output_path = tmp_path / "output.jpg"
    input_path.write_bytes(b"raw")

    captured: dict[str, object] = {}

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            captured["init"] = kwargs

        def face_blur(self, *, input: str, output: str, blur_type: str) -> Path:
            captured["call"] = {
                "input": input,
                "output": output,
                "blur_type": blur_type,
            }
            return Path(output)

        def close(self) -> None:
            captured["closed"] = True

    monkeypatch.setattr(cli, "PrivacyBlur", FakeClient)

    exit_code = cli.main(
        [
            "--api-key",
            "test-key",
            "face-blur",
            str(input_path),
            str(output_path),
            "--blur-type",
            "gaussian",
        ]
    )

    stdout = capsys.readouterr().out.strip()

    assert exit_code == 0
    assert stdout == str(output_path)
    assert captured["call"] == {
        "input": str(input_path),
        "output": str(output_path),
        "blur_type": "gaussian",
    }
    assert captured["closed"] is True
