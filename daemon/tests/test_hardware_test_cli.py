import io
import json
from collections.abc import Mapping
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

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


def test_hardware_test_cli_inspects_valid_stage_a_artifact(tmp_path: Path) -> None:
    artifact_path = tmp_path / "hardware-test-stage-a.zip"
    _write_stage_a_artifact(artifact_path)
    stdout = io.StringIO()

    exit_code = run(["inspect-artifact", str(artifact_path)], stdout=stdout)

    assert exit_code == 0
    assert json.loads(stdout.getvalue()) == {
        "status": "valid_stage_a_artifact",
        "deviceId": "mock-minix-0194",
        "profileId": "seznik-minix-s1-lyin48d-gy",
        "nextRequiredStage": "protocol_sanity_test",
    }


def test_hardware_test_cli_rejects_artifact_that_sent_print_commands(tmp_path: Path) -> None:
    artifact_path = tmp_path / "hardware-test-stage-a.zip"
    _write_stage_a_artifact(
        artifact_path,
        transfer_manifest={
            "stage": "read_only_verification",
            "deviceId": "mock-minix-0194",
            "profileId": "seznik-minix-s1-lyin48d-gy",
            "nextRequiredStage": "protocol_sanity_test",
            "printCommandsSent": True,
            "rasterBytesIncluded": False,
        },
    )
    stderr = io.StringIO()

    exit_code = run(["inspect-artifact", str(artifact_path)], stderr=stderr)

    assert exit_code == 2
    assert stderr.getvalue().strip() == "artifact is not read-only safe"


def _write_stage_a_artifact(
    artifact_path: Path,
    *,
    transfer_manifest: dict[str, object] | None = None,
) -> None:
    manifest = transfer_manifest or {
        "stage": "read_only_verification",
        "deviceId": "mock-minix-0194",
        "profileId": "seznik-minix-s1-lyin48d-gy",
        "nextRequiredStage": "protocol_sanity_test",
        "printCommandsSent": False,
        "rasterBytesIncluded": False,
    }
    with ZipFile(artifact_path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("device.json", json.dumps({"deviceId": "mock-minix-0194"}))
        archive.writestr("profile.json", json.dumps({"id": "seznik-minix-s1-lyin48d-gy"}))
        archive.writestr("ble-discovery.json", "{}")
        archive.writestr("model-response.bin", b"S1_LYiN48D_GY")
        archive.writestr("firmware-response.bin", b"V1.9.11")
        archive.writestr("notifications.log", "")
        archive.writestr("commands.log", "")
        archive.writestr("print-transfer-manifest.json", json.dumps(manifest))
        archive.writestr("band-manifest.json", json.dumps({"bands": []}))
        archive.writestr("finalizer-result.json", json.dumps({"status": "not_applicable"}))
        archive.writestr(
            "safety-report.json",
            json.dumps({"printingLocked": True, "certificationComplete": False}),
        )
        archive.writestr("user-confirmation.json", "{}")
        archive.writestr("app-version.json", "{}")
        archive.writestr("README.md", "Stage A")
