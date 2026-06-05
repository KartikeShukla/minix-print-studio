import io
import json
from collections.abc import Mapping
from pathlib import Path

from minixd.hardware_test_cli import HttpResponse, run


def test_hardware_test_cli_scans_printers_with_auth_header() -> None:
    calls: list[tuple[str, str, bytes | None, Mapping[str, str], float]] = []

    def transport(
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout: float,
    ) -> HttpResponse:
        calls.append((method, url, body, headers, timeout))
        return HttpResponse(
            status=200,
            headers={"content-type": "application/json"},
            body=json.dumps(
                {
                    "printers": [
                        {
                            "deviceId": "mock-minix-0194",
                            "name": "Seznik MiniX_0194_LE",
                        }
                    ]
                }
            ).encode("utf-8"),
        )

    stdout = io.StringIO()

    exit_code = run(
        [
            "--base-url",
            "http://127.0.0.1:39281/",
            "--token",
            "secret-token",
            "--timeout",
            "2.5",
            "scan",
        ],
        stdout=stdout,
        transport=transport,
    )

    assert exit_code == 0
    assert json.loads(stdout.getvalue())["printers"][0]["deviceId"] == "mock-minix-0194"
    assert calls == [
        (
            "POST",
            "http://127.0.0.1:39281/v1/printers/scan",
            None,
            {"Authorization": "Bearer secret-token"},
            2.5,
        )
    ]


def test_hardware_test_cli_exports_read_only_artifact_to_output_dir(tmp_path: Path) -> None:
    calls: list[tuple[str, str, bytes | None, Mapping[str, str], float]] = []

    def transport(
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout: float,
    ) -> HttpResponse:
        calls.append((method, url, body, headers, timeout))
        return HttpResponse(
            status=200,
            headers={
                "content-type": "application/zip",
                "content-disposition": 'attachment; filename="hardware-test-stage-a.zip"',
            },
            body=b"zip-bytes",
        )

    stdout = io.StringIO()

    exit_code = run(
        [
            "--base-url",
            "http://127.0.0.1:39281",
            "export-read-only",
            "--device-id",
            "mock-minix-0194",
            "--output-dir",
            str(tmp_path),
        ],
        stdout=stdout,
        transport=transport,
    )

    artifact_path = tmp_path / "hardware-test-stage-a.zip"
    assert exit_code == 0
    assert artifact_path.read_bytes() == b"zip-bytes"
    assert stdout.getvalue().strip() == str(artifact_path)
    assert calls[0][0] == "POST"
    assert calls[0][1] == "http://127.0.0.1:39281/v1/diagnostics/hardware-test"
    assert json.loads(calls[0][2] or b"{}") == {
        "deviceId": "mock-minix-0194",
        "stage": "read_only_verification",
    }


def test_hardware_test_cli_preserves_daemon_error_detail() -> None:
    def transport(
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout: float,
    ) -> HttpResponse:
        return HttpResponse(
            status=503,
            headers={"content-type": "application/json"},
            body=json.dumps(
                {"detail": "Bluetooth unavailable: Bluetooth is unsupported"}
            ).encode("utf-8"),
        )

    stderr = io.StringIO()

    exit_code = run(["scan"], stderr=stderr, transport=transport)

    assert exit_code == 2
    assert stderr.getvalue().strip() == "Bluetooth unavailable: Bluetooth is unsupported"
