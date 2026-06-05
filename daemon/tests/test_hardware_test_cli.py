import io
import json
from collections.abc import Mapping
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from minixd.hardware_test_cli import (
    HttpResponse,
    parse_macos_bluetooth_readiness,
    run,
)


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


def test_hardware_test_cli_reports_host_bluetooth_readiness() -> None:
    stdout = io.StringIO()

    exit_code = run(
        ["host-readiness"],
        stdout=stdout,
        host_bluetooth_probe=lambda: {
            "status": "not_visible",
            "platform": "Darwin",
            "controllerVisible": False,
            "canAttemptStageA": False,
            "detail": "macOS did not report a Bluetooth controller to this process.",
            "checks": [
                {
                    "name": "system_profiler SPBluetoothDataType",
                    "status": "not_visible",
                    "evidence": "controllerInfo == nil",
                }
            ],
        },
    )

    assert exit_code == 0
    assert json.loads(stdout.getvalue()) == {
        "status": "not_visible",
        "platform": "Darwin",
        "controllerVisible": False,
        "canAttemptStageA": False,
        "detail": "macOS did not report a Bluetooth controller to this process.",
        "checks": [
            {
                "name": "system_profiler SPBluetoothDataType",
                "status": "not_visible",
                "evidence": "controllerInfo == nil",
            }
        ],
    }


def test_macos_bluetooth_readiness_reports_no_visible_controller() -> None:
    result = parse_macos_bluetooth_readiness(
        stdout="Bluetooth:\n\n",
        stderr=(
            "2026-06-05 18:41:52.062 system_profiler[61351:11054831] "
            "SPBluetoothReporter getBluetoothControllerDict controllerInfo == nil\n"
        ),
        exit_code=0,
    )

    assert result == {
        "status": "not_visible",
        "platform": "Darwin",
        "controllerVisible": False,
        "canAttemptStageA": False,
        "detail": "macOS did not report a Bluetooth controller to this process.",
        "checks": [
            {
                "name": "system_profiler SPBluetoothDataType",
                "status": "not_visible",
                "evidence": "controllerInfo == nil",
            }
        ],
    }


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


def test_hardware_test_cli_plans_protocol_sanity_preflight_from_stage_a_artifact(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "hardware-test-stage-a.zip"
    _write_stage_a_artifact(artifact_path)
    stdout = io.StringIO()

    exit_code = run(["protocol-sanity-preflight", str(artifact_path)], stdout=stdout)

    assert exit_code == 0
    assert json.loads(stdout.getvalue()) == {
        "status": "protocol_sanity_preflight_ready",
        "stage": "protocol_sanity_test",
        "deviceId": "mock-minix-0194",
        "profileId": "seznik-minix-s1-lyin48d-gy",
        "writeCharacteristic": "0000ff02-0000-1000-8000-00805f9b34fb",
        "notifyCharacteristics": ["0000ff01-0000-1000-8000-00805f9b34fb"],
        "density": "medium",
        "paperMode": "continuous",
        "printCommandsSent": False,
        "rasterBytesIncluded": False,
        "commands": [
            {
                "index": 0,
                "name": "wake",
                "payloadBytes": 12,
                "hex": "00 00 00 00 00 00 00 00 00 00 00 00",
            },
            {
                "index": 1,
                "name": "set_density",
                "payloadBytes": 5,
                "hex": "10 ff 10 00 01",
            },
            {
                "index": 2,
                "name": "set_paper_mode",
                "payloadBytes": 4,
                "hex": "10 ff 84 02",
            },
        ],
        "safety": {
            "requiresPhysicalPrinter": True,
            "requiresUserConfirmation": True,
            "sendsRaster": False,
            "unlocksPrinting": False,
        },
    }


def test_hardware_test_cli_plans_tiny_visual_card_preflight_from_stage_a_artifact(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "hardware-test-stage-a.zip"
    _write_stage_a_artifact(artifact_path)
    stdout = io.StringIO()

    exit_code = run(["tiny-visual-card-preflight", str(artifact_path)], stdout=stdout)

    result = json.loads(stdout.getvalue())
    assert exit_code == 0
    assert result["status"] == "tiny_visual_card_preflight_ready"
    assert result["stage"] == "tiny_visual_test_card"
    assert result["deviceId"] == "mock-minix-0194"
    assert result["profileId"] == "seznik-minix-s1-lyin48d-gy"
    assert result["requiredPriorStage"] == "protocol_sanity_test"
    assert result["displayText"] == "MINIX TEST 7K4P"
    assert result["widthDots"] == 384
    assert result["heightDots"] == 160
    assert result["rowBytes"] == 48
    assert result["density"] == "medium"
    assert result["paperMode"] == "continuous"
    assert result["printCommandsSent"] is False
    assert result["rasterBytesIncluded"] is False
    assert result["plannedRaster"] == {
        "commandName": "raster_test_card",
        "payloadBytes": 7688,
        "rasterBytes": 7680,
        "rawBytesIncluded": False,
        "contentSha256": result["plannedRaster"]["contentSha256"],
    }
    assert len(result["plannedRaster"]["contentSha256"]) == 64
    assert result["confirmationChecklist"] == [
        "Text MINIX TEST 7K4P is readable.",
        "Left and right edge markers are visible.",
        "Output is not mirrored or upside down.",
        "Feed is smooth with no stall, overheat warning, disconnect, or fatal error.",
    ]
    assert result["safety"] == {
        "requiresPhysicalPrinter": True,
        "requiresUserConfirmation": True,
        "requiresPriorProtocolSanity": True,
        "sendsRasterIfExecuted": True,
        "unlocksPrinting": False,
        "preflightOnly": True,
    }


def test_hardware_test_cli_rejects_protocol_sanity_preflight_for_unsafe_artifact(
    tmp_path: Path,
) -> None:
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

    exit_code = run(["protocol-sanity-preflight", str(artifact_path)], stderr=stderr)

    assert exit_code == 2
    assert stderr.getvalue().strip() == "artifact is not read-only safe"


def test_hardware_test_cli_rejects_tiny_visual_card_preflight_for_unsafe_artifact(
    tmp_path: Path,
) -> None:
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

    exit_code = run(["tiny-visual-card-preflight", str(artifact_path)], stderr=stderr)

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
        archive.writestr(
            "profile.json",
            json.dumps(
                {
                    "id": "seznik-minix-s1-lyin48d-gy",
                    "ble": {
                        "writeCharUuid": "0000ff02-0000-1000-8000-00805f9b34fb",
                        "notifyCharUuids": ["0000ff01-0000-1000-8000-00805f9b34fb"],
                    },
                    "print": {
                        "widthDots": 384,
                        "rowBytes": 48,
                        "defaultDensity": "medium",
                        "defaultPaperMode": "continuous",
                    },
                }
            ),
        )
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
