import hashlib
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


def test_hardware_test_cli_guarded_scan_requires_host_readiness() -> None:
    calls: list[tuple[str, str, bytes | None, Mapping[str, str], float]] = []
    stderr = io.StringIO()

    def transport(
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout: float,
    ) -> HttpResponse:
        calls.append((method, url, body, headers, timeout))
        raise AssertionError("guarded scan must not contact the daemon when host is blocked")

    exit_code = run(
        ["scan", "--require-host-ready"],
        stderr=stderr,
        transport=transport,
        host_bluetooth_probe=lambda: {
            "status": "not_visible",
            "platform": "Darwin",
            "controllerVisible": False,
            "canAttemptStageA": False,
            "detail": "macOS did not report a Bluetooth controller to this process.",
            "recommendedActions": [
                "Open macOS System Settings > Bluetooth and confirm Bluetooth is on.",
                (
                    "Run MiniX Print Studio or scripts/hardware-test.sh from an unsandboxed "
                    "local session with Bluetooth access."
                ),
            ],
        },
    )

    assert exit_code == 2
    assert calls == []
    assert stderr.getvalue().strip() == (
        "Stage A host readiness blocked: macOS did not report a Bluetooth controller "
        "to this process. Recommended actions: Open macOS System Settings > Bluetooth "
        "and confirm Bluetooth is on.; Run MiniX Print Studio or scripts/hardware-test.sh "
        "from an unsandboxed local session with Bluetooth access."
    )


def test_hardware_test_cli_guarded_export_requires_host_readiness(tmp_path: Path) -> None:
    calls: list[tuple[str, str, bytes | None, Mapping[str, str], float]] = []
    stderr = io.StringIO()

    def transport(
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout: float,
    ) -> HttpResponse:
        calls.append((method, url, body, headers, timeout))
        raise AssertionError("guarded export must not contact the daemon when host is blocked")

    exit_code = run(
        [
            "export-read-only",
            "--device-id",
            "mock-minix-0194",
            "--output-dir",
            str(tmp_path),
            "--require-host-ready",
        ],
        stderr=stderr,
        transport=transport,
        host_bluetooth_probe=lambda: {
            "status": "not_visible",
            "platform": "Darwin",
            "controllerVisible": False,
            "canAttemptStageA": False,
            "detail": "macOS did not report a Bluetooth controller to this process.",
        },
    )

    assert exit_code == 2
    assert calls == []
    assert not list(tmp_path.iterdir())
    assert stderr.getvalue().strip() == (
        "Stage A host readiness blocked: macOS did not report a Bluetooth controller "
        "to this process."
    )


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
        "recommendedActions": [
            "Open macOS System Settings > Bluetooth and confirm Bluetooth is on.",
            (
                "Run MiniX Print Studio or scripts/hardware-test.sh from an unsandboxed "
                "local session with Bluetooth access."
            ),
            (
                "Reconnect any Bluetooth adapter or restart Bluetooth services, then rerun "
                "host-readiness before Stage A."
            ),
        ],
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


def test_hardware_test_cli_records_tiny_visual_card_artifact_from_confirmed_job(
    tmp_path: Path,
) -> None:
    stage_a_artifact_path = tmp_path / "hardware-test-stage-a.zip"
    protocol_output_dir = tmp_path / "stage-b"
    output_dir = tmp_path / "stage-c"
    _write_stage_a_artifact(stage_a_artifact_path)
    protocol_stdout = io.StringIO()
    protocol_exit_code = run(
        [
            "record-protocol-sanity",
            "--stage-a-artifact",
            str(stage_a_artifact_path),
            "--output-dir",
            str(protocol_output_dir),
            "--confirmed-at",
            "2026-06-06T12:00:00Z",
            "--operator-note",
            "Wake, density, and paper mode commands completed without error.",
            "--no-paper-moved",
            "--no-error",
        ],
        stdout=protocol_stdout,
    )
    protocol_artifact_path = Path(protocol_stdout.getvalue().strip())
    assert protocol_exit_code == 0
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
                    "jobId": "job_confirmed",
                    "previewId": "prev_tiny_card",
                    "planId": "plan_tiny_card",
                    "deviceId": "mock-minix-0194",
                    "state": "confirmed_complete",
                    "phase": "operator_confirmed",
                    "completionLevel": "verified",
                    "completionConfidence": "operator_paper_output_confirmed",
                    "requiresUserCheck": False,
                    "source": "ui",
                    "copies": 1,
                    "operatorConfirmation": {
                        "confirmedAt": "2026-06-06T12:34:56Z",
                        "printedTextReadable": True,
                        "endMarkerVisible": True,
                        "noOverheat": True,
                        "noDisconnect": True,
                        "operatorNote": "MINIX TEST 7K4P readable.",
                        "outcome": "confirmed_complete",
                    },
                    "bandsSent": 2,
                    "totalBands": 2,
                    "rowsSent": 160,
                    "totalRows": 160,
                    "bytesSent": 7680,
                    "totalBytes": 7680,
                    "tailBlankRowsDots": 0,
                    "safeActions": ["reprint_on_user_request"],
                }
            ).encode("utf-8"),
        )

    stdout = io.StringIO()

    exit_code = run(
        [
            "--base-url",
            "http://127.0.0.1:39281",
            "--token",
            "secret-token",
            "record-tiny-visual-card",
            "--stage-a-artifact",
            str(stage_a_artifact_path),
            "--protocol-sanity-artifact",
            str(protocol_artifact_path),
            "--job-id",
            "job_confirmed",
            "--output-dir",
            str(output_dir),
        ],
        stdout=stdout,
        transport=transport,
    )

    artifact_path = Path(stdout.getvalue().strip())
    assert exit_code == 0
    assert calls == [
        (
            "GET",
            "http://127.0.0.1:39281/v1/jobs/job_confirmed",
            None,
            {"Authorization": "Bearer secret-token"},
            10.0,
        )
    ]
    assert artifact_path.parent == output_dir
    assert artifact_path.name == "hardware-test-tiny-visual-card-job_confirmed.zip"
    with ZipFile(artifact_path) as archive:
        assert set(archive.namelist()) == {
            "device.json",
            "profile.json",
            "stage-a-summary.json",
            "protocol-sanity-summary.json",
            "tiny-visual-card-preflight.json",
            "job-status.json",
            "print-transfer-manifest.json",
            "band-manifest.json",
            "finalizer-result.json",
            "safety-report.json",
            "user-confirmation.json",
            "app-version.json",
            "README.md",
        }
        transfer_manifest = json.loads(archive.read("print-transfer-manifest.json"))
        protocol_summary = json.loads(archive.read("protocol-sanity-summary.json"))
        user_confirmation = json.loads(archive.read("user-confirmation.json"))
        band_manifest = json.loads(archive.read("band-manifest.json"))
        safety_report = json.loads(archive.read("safety-report.json"))
        assert b"raster" not in archive.read("job-status.json").lower()

    assert transfer_manifest == {
        "stage": "tiny_visual_test_card",
        "status": "confirmed_complete",
        "deviceId": "mock-minix-0194",
        "profileId": "seznik-minix-s1-lyin48d-gy",
        "jobId": "job_confirmed",
        "requiredPriorStage": "protocol_sanity_test",
        "nextRequiredStage": "long_print_reliability",
        "printCommandsSent": True,
        "rasterBytesIncluded": False,
        "operatorConfirmed": True,
        "completionLevel": "verified",
        "priorStageArtifactSha256": protocol_summary["artifactSha256"],
    }
    assert protocol_summary == {
        "stage": "protocol_sanity_test",
        "status": "confirmed_complete",
        "deviceId": "mock-minix-0194",
        "profileId": "seznik-minix-s1-lyin48d-gy",
        "confirmedAt": "2026-06-06T12:00:00Z",
        "artifactSha256": hashlib.sha256(protocol_artifact_path.read_bytes()).hexdigest(),
    }
    assert user_confirmation["outcome"] == "confirmed_complete"
    assert user_confirmation["operatorNote"] == "MINIX TEST 7K4P readable."
    assert band_manifest == {
        "bandsSent": 2,
        "totalBands": 2,
        "rowsSent": 160,
        "totalRows": 160,
        "bytesSent": 7680,
        "totalBytes": 7680,
        "rasterBytesIncluded": False,
    }
    assert safety_report == {
        "stage": "tiny_visual_test_card",
        "printingLocked": True,
        "certificationComplete": False,
        "requiresLongPrintReliability": True,
        "rasterBytesIncluded": False,
        "unlocksPrinting": False,
    }


def test_hardware_test_cli_records_protocol_sanity_artifact_from_operator_check(
    tmp_path: Path,
) -> None:
    stage_a_artifact_path = tmp_path / "hardware-test-stage-a.zip"
    output_dir = tmp_path / "stage-b"
    _write_stage_a_artifact(stage_a_artifact_path)
    stdout = io.StringIO()

    exit_code = run(
        [
            "record-protocol-sanity",
            "--stage-a-artifact",
            str(stage_a_artifact_path),
            "--output-dir",
            str(output_dir),
            "--confirmed-at",
            "2026-06-06T12:00:00Z",
            "--operator-note",
            "Wake, density, and paper mode commands completed without error.",
            "--no-paper-moved",
            "--no-error",
        ],
        stdout=stdout,
    )

    artifact_path = Path(stdout.getvalue().strip())
    assert exit_code == 0
    assert artifact_path.parent == output_dir
    assert artifact_path.name == "hardware-test-protocol-sanity.zip"
    with ZipFile(artifact_path) as archive:
        assert set(archive.namelist()) == {
            "device.json",
            "profile.json",
            "stage-a-summary.json",
            "protocol-sanity-preflight.json",
            "commands.log",
            "print-transfer-manifest.json",
            "finalizer-result.json",
            "safety-report.json",
            "user-confirmation.json",
            "app-version.json",
            "README.md",
        }
        transfer_manifest = json.loads(archive.read("print-transfer-manifest.json"))
        user_confirmation = json.loads(archive.read("user-confirmation.json"))
        safety_report = json.loads(archive.read("safety-report.json"))
        commands_log = archive.read("commands.log").decode("utf-8")

    assert transfer_manifest == {
        "stage": "protocol_sanity_test",
        "status": "confirmed_complete",
        "deviceId": "mock-minix-0194",
        "profileId": "seznik-minix-s1-lyin48d-gy",
        "requiredPriorStage": "read_only_verification",
        "nextRequiredStage": "tiny_visual_test_card",
        "printCommandsSent": True,
        "rasterBytesIncluded": False,
        "operatorConfirmed": True,
        "completionLevel": "verified",
    }
    assert user_confirmation == {
        "confirmedAt": "2026-06-06T12:00:00Z",
        "noPaperMoved": True,
        "noError": True,
        "operatorNote": "Wake, density, and paper mode commands completed without error.",
        "outcome": "confirmed_complete",
    }
    assert safety_report == {
        "stage": "protocol_sanity_test",
        "printingLocked": True,
        "certificationComplete": False,
        "requiresTinyVisualCard": True,
        "rasterBytesIncluded": False,
        "unlocksPrinting": False,
    }
    assert "wake" in commands_log
    assert "set_density" in commands_log
    assert "set_paper_mode" in commands_log


def test_hardware_test_cli_writes_shareable_evidence_summary_without_private_artifact_data(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "hardware-test-stage-a.zip"
    _write_stage_a_artifact(
        artifact_path,
        commands_log="/Users/example/private-token 10 ff 10 00 01",
        notifications_log="S1_LYiN48D_GY raw-notification",
    )
    stdout = io.StringIO()

    exit_code = run(["evidence-summary", str(artifact_path)], stdout=stdout)

    assert exit_code == 0
    result = json.loads(stdout.getvalue())
    encoded = json.dumps(result, sort_keys=True)
    device_fingerprint = hashlib.sha256(b"mock-minix-0194").hexdigest()[:16]
    assert result == {
        "status": "shareable_stage_a_evidence_ready",
        "shareable": True,
        "artifactStatus": "valid_stage_a_artifact",
        "profileId": "seznik-minix-s1-lyin48d-gy",
        "nextRequiredStage": "protocol_sanity_test",
        "device": {
            "idRedacted": True,
            "fingerprint": f"sha256:{device_fingerprint}",
        },
        "redaction": {
            "artifactPathIncluded": False,
            "localPathsIncluded": False,
            "rawCommandLogIncluded": False,
            "rawNotificationLogIncluded": False,
            "commandPayloadHexIncluded": False,
            "rasterBytesIncluded": False,
            "bearerTokensIncluded": False,
        },
        "certification": {
            "stageAReadOnlyVerified": True,
            "printingLocked": True,
            "certificationComplete": False,
            "requiresStageBProtocolSanity": True,
            "requiresTinyVisualCard": True,
            "requiresLongPrintReliability": True,
        },
        "preflights": {
            "protocolSanity": {
                "status": "protocol_sanity_preflight_ready",
                "stage": "protocol_sanity_test",
                "commandCount": 3,
                "sendsRaster": False,
                "unlocksPrinting": False,
            },
            "tinyVisualCard": {
                "status": "tiny_visual_card_preflight_ready",
                "stage": "tiny_visual_test_card",
                "displayText": "MINIX TEST 7K4P",
                "heightDots": 160,
                "rawBytesIncluded": False,
                "contentSha256": result["preflights"]["tinyVisualCard"]["contentSha256"],
            },
        },
    }
    assert len(result["preflights"]["tinyVisualCard"]["contentSha256"]) == 64
    assert str(artifact_path) not in encoded
    assert "/Users/example" not in encoded
    assert "private-token" not in encoded
    assert "mock-minix-0194" not in encoded
    assert "10 ff 10 00 01" not in encoded
    assert "S1_LYiN48D_GY" not in encoded


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
    commands_log: str = "",
    notifications_log: str = "",
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
        archive.writestr("notifications.log", notifications_log)
        archive.writestr("commands.log", commands_log)
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
