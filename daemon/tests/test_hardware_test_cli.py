import base64
import hashlib
import io
import json
from collections.abc import Mapping
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from minixd.hardware_test_cli import (
    HttpResponse,
    parse_macos_bluetooth_readiness,
    run,
)


def test_hardware_test_cli_help_omits_token_argument(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        run(["--help"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    assert "--token" not in captured.out
    assert "MINIX_DAEMON_TOKEN" in captured.out


def test_hardware_test_cli_scans_printers_with_auth_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MINIX_DAEMON_TOKEN", "secret-token")
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
    assert stdout.getvalue().strip() == "artifact-exported"
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
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("MINIX_DAEMON_TOKEN", "secret-token")
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
    protocol_artifact_path = protocol_output_dir / "hardware-test-protocol-sanity.zip"
    assert protocol_exit_code == 0
    assert protocol_stdout.getvalue().strip() == "protocol-sanity-recorded"
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

    artifact_path = output_dir / "hardware-test-tiny-visual-card-job_confirmed.zip"
    assert exit_code == 0
    assert stdout.getvalue().strip() == "tiny-visual-card-recorded"
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

    artifact_path = output_dir / "hardware-test-protocol-sanity.zip"
    assert exit_code == 0
    assert stdout.getvalue().strip() == "protocol-sanity-recorded"
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


def test_hardware_test_cli_records_trusted_printer_record_without_long_print_unlock(
    tmp_path: Path,
) -> None:
    stage_a_artifact_path = tmp_path / "hardware-test-stage-a.zip"
    protocol_output_dir = tmp_path / "stage-b"
    tiny_output_dir = tmp_path / "stage-c"
    trusted_output_dir = tmp_path / "trusted"
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
            "Protocol commands completed without paper motion or fatal error.",
            "--no-paper-moved",
            "--no-error",
        ],
        stdout=protocol_stdout,
    )
    protocol_artifact_path = protocol_output_dir / "hardware-test-protocol-sanity.zip"
    assert protocol_exit_code == 0
    assert protocol_stdout.getvalue().strip() == "protocol-sanity-recorded"
    tiny_stdout = io.StringIO()
    tiny_exit_code = run(
        [
            "--base-url",
            "http://127.0.0.1:39281",
            "record-tiny-visual-card",
            "--stage-a-artifact",
            str(stage_a_artifact_path),
            "--protocol-sanity-artifact",
            str(protocol_artifact_path),
            "--job-id",
            "job_confirmed",
            "--output-dir",
            str(tiny_output_dir),
        ],
        stdout=tiny_stdout,
        transport=_confirmed_tiny_card_transport,
    )
    tiny_artifact_path = tiny_output_dir / "hardware-test-tiny-visual-card-job_confirmed.zip"
    assert tiny_exit_code == 0
    assert tiny_stdout.getvalue().strip() == "tiny-visual-card-recorded"
    stdout = io.StringIO()

    exit_code = run(
        [
            "record-trusted-printer",
            "--stage-a-artifact",
            str(stage_a_artifact_path),
            "--protocol-sanity-artifact",
            str(protocol_artifact_path),
            "--tiny-visual-card-artifact",
            str(tiny_artifact_path),
            "--output-dir",
            str(trusted_output_dir),
        ],
        stdout=stdout,
    )

    device_fingerprint = f"sha256:{hashlib.sha256(b'mock-minix-0194').hexdigest()[:16]}"
    record_path = (
        trusted_output_dir
        / f"trusted-printer-{device_fingerprint.removeprefix('sha256:')}.json"
    )
    assert exit_code == 0
    assert stdout.getvalue().strip() == "trusted-printer-recorded"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record.pop("trustedAt").endswith("Z")
    assert record == {
        "schemaVersion": 1,
        "status": "trusted_for_manual_continuous_printing",
        "device": {
            "idRedacted": True,
            "fingerprint": device_fingerprint,
        },
        "profileId": "seznik-minix-s1-lyin48d-gy",
        "operatorNoteIncluded": False,
        "trustedFor": ["manual_continuous_printing"],
        "hardwareEvidence": {
            "stageA": {
                "stage": "read_only_verification",
                "status": "valid_stage_a_artifact",
                "artifactSha256": hashlib.sha256(stage_a_artifact_path.read_bytes()).hexdigest(),
            },
            "protocolSanity": {
                "stage": "protocol_sanity_test",
                "status": "confirmed_complete",
                "artifactSha256": hashlib.sha256(
                    protocol_artifact_path.read_bytes()
                ).hexdigest(),
            },
            "tinyVisualCard": {
                "stage": "tiny_visual_test_card",
                "status": "confirmed_complete",
                "jobId": "job_confirmed",
                "artifactSha256": hashlib.sha256(tiny_artifact_path.read_bytes()).hexdigest(),
            },
        },
        "safety": {
            "manualContinuousPrintingEnabled": True,
            "longPrintReliabilityRequired": True,
            "longPrintPrintingEnabled": False,
            "agentDirectPrintingEnabled": False,
            "stableSupportClaimEnabled": False,
        },
        "nextRequiredStage": "long_print_reliability",
    }


def test_hardware_test_cli_records_long_print_reliability_artifact_without_stable_unlock(
    tmp_path: Path,
) -> None:
    stage_a_artifact_path = tmp_path / "hardware-test-stage-a.zip"
    protocol_output_dir = tmp_path / "stage-b"
    tiny_output_dir = tmp_path / "stage-c"
    trusted_output_dir = tmp_path / "trusted"
    long_print_output_dir = tmp_path / "stage-d"
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
            "Protocol commands completed without paper motion or fatal error.",
            "--no-paper-moved",
            "--no-error",
        ],
        stdout=protocol_stdout,
    )
    protocol_artifact_path = protocol_output_dir / "hardware-test-protocol-sanity.zip"
    assert protocol_exit_code == 0
    tiny_stdout = io.StringIO()
    tiny_exit_code = run(
        [
            "--base-url",
            "http://127.0.0.1:39281",
            "record-tiny-visual-card",
            "--stage-a-artifact",
            str(stage_a_artifact_path),
            "--protocol-sanity-artifact",
            str(protocol_artifact_path),
            "--job-id",
            "job_confirmed",
            "--output-dir",
            str(tiny_output_dir),
        ],
        stdout=tiny_stdout,
        transport=_confirmed_tiny_card_transport,
    )
    tiny_artifact_path = tiny_output_dir / "hardware-test-tiny-visual-card-job_confirmed.zip"
    assert tiny_exit_code == 0
    trusted_stdout = io.StringIO()
    trusted_exit_code = run(
        [
            "record-trusted-printer",
            "--stage-a-artifact",
            str(stage_a_artifact_path),
            "--protocol-sanity-artifact",
            str(protocol_artifact_path),
            "--tiny-visual-card-artifact",
            str(tiny_artifact_path),
            "--output-dir",
            str(trusted_output_dir),
        ],
        stdout=trusted_stdout,
    )
    device_fingerprint = f"sha256:{hashlib.sha256(b'mock-minix-0194').hexdigest()[:16]}"
    trusted_record_path = (
        trusted_output_dir
        / f"trusted-printer-{device_fingerprint.removeprefix('sha256:')}.json"
    )
    assert trusted_exit_code == 0
    stdout = io.StringIO()

    exit_code = run(
        [
            "--base-url",
            "http://127.0.0.1:39281",
            "record-long-print-reliability",
            "--stage-a-artifact",
            str(stage_a_artifact_path),
            "--protocol-sanity-artifact",
            str(protocol_artifact_path),
            "--tiny-visual-card-artifact",
            str(tiny_artifact_path),
            "--trusted-printer-record",
            str(trusted_record_path),
            "--job-id",
            "job_long_confirmed",
            "--output-dir",
            str(long_print_output_dir),
        ],
        stdout=stdout,
        transport=_confirmed_long_print_transport,
    )

    artifact_path = (
        long_print_output_dir
        / "hardware-test-long-print-reliability-job_long_confirmed.zip"
    )
    assert exit_code == 0
    assert stdout.getvalue().strip() == "long-print-reliability-recorded"
    with ZipFile(artifact_path) as archive:
        assert set(archive.namelist()) == {
            "stage-chain-summary.json",
            "trusted-printer-summary.json",
            "long-print-job-summary.json",
            "print-transfer-manifest.json",
            "band-manifest.json",
            "finalizer-result.json",
            "safety-report.json",
            "user-confirmation.json",
            "README.md",
        }
        stage_chain = json.loads(archive.read("stage-chain-summary.json"))
        trusted_summary = json.loads(archive.read("trusted-printer-summary.json"))
        job_summary = json.loads(archive.read("long-print-job-summary.json"))
        transfer_manifest = json.loads(archive.read("print-transfer-manifest.json"))
        band_manifest = json.loads(archive.read("band-manifest.json"))
        finalizer_result = json.loads(archive.read("finalizer-result.json"))
        safety_report = json.loads(archive.read("safety-report.json"))
        user_confirmation = json.loads(archive.read("user-confirmation.json"))

    assert stage_chain == {
        "stageA": {
            "stage": "read_only_verification",
            "status": "valid_stage_a_artifact",
            "artifactSha256": hashlib.sha256(stage_a_artifact_path.read_bytes()).hexdigest(),
        },
        "protocolSanity": {
            "stage": "protocol_sanity_test",
            "status": "confirmed_complete",
            "artifactSha256": hashlib.sha256(protocol_artifact_path.read_bytes()).hexdigest(),
        },
        "tinyVisualCard": {
            "stage": "tiny_visual_test_card",
            "status": "confirmed_complete",
            "artifactSha256": hashlib.sha256(tiny_artifact_path.read_bytes()).hexdigest(),
        },
        "trustedPrinter": {
            "status": "trusted_for_manual_continuous_printing",
            "artifactSha256": hashlib.sha256(trusted_record_path.read_bytes()).hexdigest(),
        },
    }
    assert trusted_summary == {
        "status": "trusted_for_manual_continuous_printing",
        "device": {
            "idRedacted": True,
            "fingerprint": device_fingerprint,
        },
        "profileId": "seznik-minix-s1-lyin48d-gy",
        "trustedFor": ["manual_continuous_printing"],
    }
    assert job_summary == {
        "jobId": "job_long_confirmed",
        "profileId": "seznik-minix-s1-lyin48d-gy",
        "device": {
            "idRedacted": True,
            "fingerprint": device_fingerprint,
        },
        "state": "confirmed_complete",
        "completionLevel": "verified",
        "completionConfidence": "operator_paper_output_confirmed",
        "requiresUserCheck": False,
        "rasterBytesIncluded": False,
        "operatorNoteIncluded": False,
    }
    assert transfer_manifest == {
        "stage": "long_print_reliability",
        "status": "confirmed_complete",
        "profileId": "seznik-minix-s1-lyin48d-gy",
        "jobId": "job_long_confirmed",
        "requiredPriorStage": "trusted_printer_record",
        "nextRequiredStage": "maintainer_review_for_stable_support",
        "printCommandsSent": True,
        "rasterBytesIncluded": False,
        "operatorConfirmed": True,
        "completionLevel": "verified",
        "longPrintReliabilityPassed": True,
        "priorStageArtifactSha256": hashlib.sha256(
            trusted_record_path.read_bytes()
        ).hexdigest(),
    }
    assert band_manifest == {
        "bandsSent": 32,
        "totalBands": 32,
        "rowsSent": 8160,
        "totalRows": 8160,
        "bytesSent": 391680,
        "totalBytes": 391680,
        "tailBlankRowsDots": 160,
        "rasterBytesIncluded": False,
        "requiresLongPrintMode": True,
    }
    assert finalizer_result == {
        "state": "confirmed_complete",
        "phase": "operator_confirmed",
        "completionConfidence": "operator_paper_output_confirmed",
    }
    assert safety_report == {
        "stage": "long_print_reliability",
        "longPrintReliabilityPassed": True,
        "manualContinuousPrintingAlreadyTrusted": True,
        "certificationComplete": False,
        "stableSupportClaimEnabled": False,
        "agentDirectPrintingEnabled": False,
        "rasterBytesIncluded": False,
    }
    assert user_confirmation == {
        "confirmedAt": "2026-06-06T12:45:00Z",
        "printedTextReadable": True,
        "endMarkerVisible": True,
        "noOverheat": True,
        "noDisconnect": True,
        "outcome": "confirmed_complete",
        "operatorNoteIncluded": False,
    }
    encoded_artifact = json.dumps(
        {
            "stage_chain": stage_chain,
            "trusted_summary": trusted_summary,
            "job_summary": job_summary,
            "transfer_manifest": transfer_manifest,
            "band_manifest": band_manifest,
            "finalizer_result": finalizer_result,
            "safety_report": safety_report,
            "user_confirmation": user_confirmation,
        },
        sort_keys=True,
    )
    assert "mock-minix-0194" not in encoded_artifact
    assert "END LP-TEST checksum" not in encoded_artifact


def test_hardware_test_cli_prints_long_print_reliability_fixture_without_unlock(
    tmp_path: Path,
) -> None:
    chain = _create_trusted_printer_chain(tmp_path)
    stdout = io.StringIO()
    calls: list[tuple[str, str, dict[str, object] | None]] = []
    render_request: dict[str, object] = {}

    def transport(
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout: float,
    ) -> HttpResponse:
        decoded_body = json.loads(body or b"{}") if body is not None else None
        calls.append((method, url, decoded_body))
        if url.endswith("/v1/render/preview"):
            assert decoded_body is not None
            assert timeout == 10.0
            render_request.update(decoded_body)
            raster = base64.b64decode(str(decoded_body["rasterBase64"]), validate=True)
            assert decoded_body["profileId"] == "seznik-minix-s1-lyin48d-gy"
            assert decoded_body["widthDots"] == 384
            assert decoded_body["heightDots"] == 8000
            assert len(raster) == 384000
            assert "mock-minix-0194" not in json.dumps(decoded_body, sort_keys=True)
            return HttpResponse(
                status=200,
                headers={"content-type": "application/json"},
                body=json.dumps(
                    {
                        "previewId": "prev_long_print_fixture",
                        "approvalToken": "appr_long_print_fixture",
                        "documentHash": decoded_body["documentHash"],
                        "renderSettingsHash": decoded_body["renderSettingsHash"],
                        "rasterHash": "sha256:preview-raster",
                        "profileId": decoded_body["profileId"],
                        "widthDots": decoded_body["widthDots"],
                        "heightDots": decoded_body["heightDots"],
                        "safety": {"allowed": True, "errors": []},
                        "createdAt": "2026-06-06T12:30:00Z",
                        "expiresAt": "2026-06-06T12:40:00Z",
                    }
                ).encode("utf-8"),
            )
        if url.endswith("/v1/jobs/print"):
            assert timeout == 600.0
            assert decoded_body == {
                "previewId": "prev_long_print_fixture",
                "approvalToken": "appr_long_print_fixture",
                "documentHash": render_request["documentHash"],
                "renderSettingsHash": render_request["renderSettingsHash"],
                "profileId": "seznik-minix-s1-lyin48d-gy",
                "paperMode": "continuous",
                "density": "medium",
                "copies": 1,
                "source": "hardware-test-long-print-reliability",
                "deviceId": "mock-minix-0194",
            }
            return HttpResponse(
                status=200,
                headers={"content-type": "application/json"},
                body=json.dumps(
                    {
                        "jobId": "job_long_print_started",
                        "previewId": "prev_long_print_fixture",
                        "planId": "plan_job_long_print_started",
                        "deviceId": "mock-minix-0194",
                        "state": "completed_unverified",
                        "phase": "waiting_for_user_confirmation",
                        "completionLevel": "unverified",
                        "completionConfidence": "ble_transfer_completed_final_ack_unverified",
                        "requiresUserCheck": True,
                        "source": "hardware-test-long-print-reliability",
                        "copies": 1,
                        "operatorConfirmation": None,
                        "bandsSent": 32,
                        "totalBands": 32,
                        "rowsSent": 8160,
                        "totalRows": 8160,
                        "bytesSent": 391680,
                        "totalBytes": 391680,
                        "tailBlankRowsDots": 160,
                        "safeActions": ["confirm_complete", "feed_paper", "reprint_from_start"],
                    }
                ).encode("utf-8"),
            )
        raise AssertionError(f"unexpected daemon request: {method} {url}")

    exit_code = run(
        [
            "--base-url",
            "http://127.0.0.1:39281",
            "print-long-print-reliability",
            "--stage-a-artifact",
            str(chain["stage_a"]),
            "--protocol-sanity-artifact",
            str(chain["protocol_sanity"]),
            "--tiny-visual-card-artifact",
            str(chain["tiny_visual_card"]),
            "--trusted-printer-record",
            str(chain["trusted_printer"]),
        ],
        stdout=stdout,
        transport=transport,
    )

    assert exit_code == 0
    assert stdout.getvalue().strip() == "long-print-reliability-print-started"
    assert [call[1] for call in calls] == [
        "http://127.0.0.1:39281/v1/render/preview",
        "http://127.0.0.1:39281/v1/jobs/print",
    ]
    assert "mock-minix-0194" not in stdout.getvalue()
    assert "rasterBase64" not in stdout.getvalue()


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


def _confirmed_tiny_card_transport(
    method: str,
    url: str,
    body: bytes | None,
    headers: Mapping[str, str],
    timeout: float,
) -> HttpResponse:
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


def _confirmed_long_print_transport(
    method: str,
    url: str,
    body: bytes | None,
    headers: Mapping[str, str],
    timeout: float,
) -> HttpResponse:
    return HttpResponse(
        status=200,
        headers={"content-type": "application/json"},
        body=json.dumps(
            {
                "jobId": "job_long_confirmed",
                "previewId": "prev_long_print",
                "planId": "plan_long_print",
                "deviceId": "mock-minix-0194",
                "state": "confirmed_complete",
                "phase": "operator_confirmed",
                "completionLevel": "verified",
                "completionConfidence": "operator_paper_output_confirmed",
                "requiresUserCheck": False,
                "source": "ui",
                "copies": 1,
                "operatorConfirmation": {
                    "confirmedAt": "2026-06-06T12:45:00Z",
                    "printedTextReadable": True,
                    "endMarkerVisible": True,
                    "noOverheat": True,
                    "noDisconnect": True,
                    "operatorNote": "END LP-TEST checksum: 7F3A visible.",
                    "outcome": "confirmed_complete",
                },
                "bandsSent": 32,
                "totalBands": 32,
                "rowsSent": 8160,
                "totalRows": 8160,
                "bytesSent": 391680,
                "totalBytes": 391680,
                "tailBlankRowsDots": 160,
                "safeActions": ["reprint_on_user_request"],
            }
        ).encode("utf-8"),
    )


def _create_trusted_printer_chain(tmp_path: Path) -> dict[str, object]:
    stage_a_artifact_path = tmp_path / "hardware-test-stage-a.zip"
    protocol_output_dir = tmp_path / "stage-b"
    tiny_output_dir = tmp_path / "stage-c"
    trusted_output_dir = tmp_path / "trusted"
    _write_stage_a_artifact(stage_a_artifact_path)
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
            "Protocol commands completed without paper motion or fatal error.",
            "--no-paper-moved",
            "--no-error",
        ],
        stdout=io.StringIO(),
    )
    protocol_artifact_path = protocol_output_dir / "hardware-test-protocol-sanity.zip"
    tiny_exit_code = run(
        [
            "--base-url",
            "http://127.0.0.1:39281",
            "record-tiny-visual-card",
            "--stage-a-artifact",
            str(stage_a_artifact_path),
            "--protocol-sanity-artifact",
            str(protocol_artifact_path),
            "--job-id",
            "job_confirmed",
            "--output-dir",
            str(tiny_output_dir),
        ],
        stdout=io.StringIO(),
        transport=_confirmed_tiny_card_transport,
    )
    tiny_artifact_path = tiny_output_dir / "hardware-test-tiny-visual-card-job_confirmed.zip"
    trusted_exit_code = run(
        [
            "record-trusted-printer",
            "--stage-a-artifact",
            str(stage_a_artifact_path),
            "--protocol-sanity-artifact",
            str(protocol_artifact_path),
            "--tiny-visual-card-artifact",
            str(tiny_artifact_path),
            "--output-dir",
            str(trusted_output_dir),
        ],
        stdout=io.StringIO(),
    )
    device_fingerprint = f"sha256:{hashlib.sha256(b'mock-minix-0194').hexdigest()[:16]}"
    trusted_record_path = (
        trusted_output_dir
        / f"trusted-printer-{device_fingerprint.removeprefix('sha256:')}.json"
    )
    assert protocol_exit_code == 0
    assert tiny_exit_code == 0
    assert trusted_exit_code == 0
    return {
        "stage_a": stage_a_artifact_path,
        "protocol_sanity": protocol_artifact_path,
        "tiny_visual_card": tiny_artifact_path,
        "trusted_printer": trusted_record_path,
        "device_fingerprint": device_fingerprint,
    }


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
