from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO, cast
from zipfile import BadZipFile, ZipFile

from minixd.protocol.aiyin import (
    build_raster_command,
    build_set_density_command,
    build_set_paper_mode_command,
    build_wake_command,
)


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


type HttpTransport = Callable[[str, str, bytes | None, Mapping[str, str], float], HttpResponse]
type HostBluetoothProbe = Callable[[], dict[str, object]]


class HardwareTestCliError(RuntimeError):
    """Raised when the hardware-test CLI cannot complete the requested operation."""


_MACOS_BLUETOOTH_NOT_VISIBLE_ACTIONS = [
    "Open macOS System Settings > Bluetooth and confirm Bluetooth is on.",
    (
        "Run MiniX Print Studio or scripts/hardware-test.sh from an unsandboxed "
        "local session with Bluetooth access."
    ),
    (
        "Reconnect any Bluetooth adapter or restart Bluetooth services, then rerun "
        "host-readiness before Stage A."
    ),
]
_MACOS_BLUETOOTH_UNKNOWN_ACTIONS = [
    "Review system_profiler SPBluetoothDataType output from an unsandboxed terminal.",
    "Confirm macOS Bluetooth permissions and adapter visibility before retrying Stage A.",
]
_MACOS_BLUETOOTH_READY_ACTIONS = [
    "Continue with scripts/hardware-test.sh scan while the printer is powered on and nearby.",
]
_UNSUPPORTED_BLUETOOTH_PLATFORM_ACTIONS = [
    "Run Stage A host-readiness and scan from macOS until this platform is certified.",
]


STAGE_A_ARTIFACT_REQUIRED_FILES = (
    "device.json",
    "profile.json",
    "ble-discovery.json",
    "model-response.bin",
    "firmware-response.bin",
    "notifications.log",
    "commands.log",
    "print-transfer-manifest.json",
    "band-manifest.json",
    "finalizer-result.json",
    "safety-report.json",
    "user-confirmation.json",
    "app-version.json",
    "README.md",
)
TINY_VISUAL_CARD_TEXT = "MINIX TEST 7K4P"
TINY_VISUAL_CARD_HEIGHT_DOTS = 160
TINY_VISUAL_CARD_CONFIRMATION_CHECKLIST = (
    "Text MINIX TEST 7K4P is readable.",
    "Left and right edge markers are visible.",
    "Output is not mirrored or upside down.",
    "Feed is smooth with no stall, overheat warning, disconnect, or fatal error.",
)
_TINY_CARD_FONT: dict[str, tuple[str, ...]] = {
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    "4": ("10010", "10010", "10010", "11111", "00010", "00010", "00010"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "X": ("10001", "01010", "00100", "00100", "00100", "01010", "10001"),
}


class HardwareTestClient:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        timeout: float,
        transport: HttpTransport,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._transport = transport

    def scan_printers(self) -> dict[str, object]:
        return self._request_json("POST", "/v1/printers/scan")

    def export_read_only_artifact(self, *, device_id: str, output_dir: Path) -> Path:
        response = self._request(
            "POST",
            "/v1/diagnostics/hardware-test",
            body={"deviceId": device_id, "stage": "read_only_verification"},
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = _artifact_filename(response.headers)
        artifact_path = output_dir / filename
        artifact_path.write_bytes(response.body)
        return artifact_path

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
    ) -> dict[str, object]:
        response = self._request(method, path, body=body)
        try:
            decoded = json.loads(response.body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise HardwareTestCliError("daemon returned invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise HardwareTestCliError("daemon returned non-object JSON")
        return cast(dict[str, object], decoded)

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
    ) -> HttpResponse:
        headers: dict[str, str] = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        encoded_body: bytes | None = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            encoded_body = json.dumps(body).encode("utf-8")

        response = self._transport(
            method,
            f"{self._base_url}{path}",
            encoded_body,
            headers,
            self._timeout,
        )
        if response.status >= 400:
            raise HardwareTestCliError(_error_detail(response))
        return response


def run(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    transport: HttpTransport | None = None,
    host_bluetooth_probe: HostBluetoothProbe | None = None,
) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    client = HardwareTestClient(
        base_url=args.base_url,
        token=args.token,
        timeout=args.timeout,
        transport=transport or urllib_transport,
    )

    try:
        if args.command == "scan":
            stdout.write(json.dumps(client.scan_printers(), indent=2, sort_keys=True))
            stdout.write("\n")
            return 0
        if args.command == "host-readiness":
            probe_result = (
                host_bluetooth_probe or collect_host_bluetooth_readiness
            )()
            stdout.write(json.dumps(probe_result, indent=2, sort_keys=True))
            stdout.write("\n")
            return 0
        if args.command == "export-read-only":
            artifact_path = client.export_read_only_artifact(
                device_id=args.device_id,
                output_dir=Path(args.output_dir),
            )
            stdout.write(f"{artifact_path}\n")
            return 0
        if args.command == "inspect-artifact":
            stdout.write(
                json.dumps(
                    inspect_stage_a_artifact(Path(args.artifact_path)),
                    indent=2,
                    sort_keys=True,
                )
            )
            stdout.write("\n")
            return 0
        if args.command == "protocol-sanity-preflight":
            stdout.write(
                json.dumps(
                    plan_protocol_sanity_preflight(Path(args.artifact_path)),
                    indent=2,
                    sort_keys=True,
                )
            )
            stdout.write("\n")
            return 0
        if args.command == "tiny-visual-card-preflight":
            stdout.write(
                json.dumps(
                    plan_tiny_visual_card_preflight(Path(args.artifact_path)),
                    indent=2,
                    sort_keys=True,
                )
            )
            stdout.write("\n")
            return 0
        if args.command == "evidence-summary":
            stdout.write(
                json.dumps(
                    build_shareable_evidence_summary(Path(args.artifact_path)),
                    indent=2,
                    sort_keys=True,
                )
            )
            stdout.write("\n")
            return 0
    except HardwareTestCliError as exc:
        stderr.write(f"{exc}\n")
        return 2

    stderr.write(f"unsupported command: {args.command}\n")
    return 2


def main() -> None:
    raise SystemExit(run())


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="minix-hardware-test",
        description="Run MiniX Print Studio hardware validation helpers against a local daemon.",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MINIX_DAEMON_BASE_URL", "http://127.0.0.1:39281"),
        help="Daemon base URL. Defaults to MINIX_DAEMON_BASE_URL or localhost.",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("MINIX_DAEMON_TOKEN", ""),
        help="Daemon bearer token. Defaults to MINIX_DAEMON_TOKEN.",
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds.")

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("scan", help="Scan for visible printer candidates.")
    subparsers.add_parser(
        "host-readiness",
        help="Check whether the host exposes a Bluetooth controller for Stage A.",
    )

    export_parser = subparsers.add_parser(
        "export-read-only",
        help="Export the Stage A read-only hardware-test artifact for a device id.",
    )
    export_parser.add_argument("--device-id", required=True, help="Device id from scan output.")
    export_parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for the hardware-test ZIP artifact.",
    )

    inspect_parser = subparsers.add_parser(
        "inspect-artifact",
        help="Inspect a Stage A hardware-test ZIP artifact without contacting the daemon.",
    )
    inspect_parser.add_argument("artifact_path", help="Path to a Stage A hardware-test ZIP.")

    preflight_parser = subparsers.add_parser(
        "protocol-sanity-preflight",
        help="Plan the Stage B protocol sanity command sequence from a Stage A artifact.",
    )
    preflight_parser.add_argument("artifact_path", help="Path to a Stage A hardware-test ZIP.")

    visual_card_parser = subparsers.add_parser(
        "tiny-visual-card-preflight",
        help="Plan the Stage C tiny visual card metadata from a Stage A artifact.",
    )
    visual_card_parser.add_argument(
        "artifact_path",
        help="Path to a Stage A hardware-test ZIP.",
    )

    evidence_summary_parser = subparsers.add_parser(
        "evidence-summary",
        help="Build a redacted, shareable Stage A evidence summary.",
    )
    evidence_summary_parser.add_argument(
        "artifact_path",
        help="Path to a Stage A hardware-test ZIP.",
    )
    return parser


def inspect_stage_a_artifact(artifact_path: Path) -> dict[str, object]:
    try:
        with ZipFile(artifact_path) as archive:
            _require_stage_a_artifact_files(archive)
            transfer_manifest = _read_zip_json_object(
                archive,
                "print-transfer-manifest.json",
            )
            safety_report = _read_zip_json_object(archive, "safety-report.json")
    except FileNotFoundError as exc:
        raise HardwareTestCliError("artifact not found") from exc
    except BadZipFile as exc:
        raise HardwareTestCliError("artifact is not a ZIP file") from exc

    _validate_read_only_safety(transfer_manifest, safety_report)
    return {
        "status": "valid_stage_a_artifact",
        "deviceId": _required_json_string(
            transfer_manifest,
            "deviceId",
            "print-transfer-manifest.json",
        ),
        "profileId": _required_json_string(
            transfer_manifest,
            "profileId",
            "print-transfer-manifest.json",
        ),
        "nextRequiredStage": _required_json_string(
            transfer_manifest,
            "nextRequiredStage",
            "print-transfer-manifest.json",
        ),
    }


def collect_host_bluetooth_readiness() -> dict[str, object]:
    host_platform = platform.system()
    if host_platform == "Darwin":
        try:
            completed = subprocess.run(
                ["system_profiler", "SPBluetoothDataType"],
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {
                "status": "unknown",
                "platform": host_platform,
                "controllerVisible": None,
                "canAttemptStageA": False,
                "detail": f"Could not run macOS Bluetooth readiness probe: {exc}",
                "recommendedActions": _MACOS_BLUETOOTH_UNKNOWN_ACTIONS,
                "checks": [
                    {
                        "name": "system_profiler SPBluetoothDataType",
                        "status": "unknown",
                        "evidence": type(exc).__name__,
                    }
                ],
            }
        return parse_macos_bluetooth_readiness(
            stdout=completed.stdout,
            stderr=completed.stderr,
            exit_code=completed.returncode,
        )

    return {
        "status": "unsupported_platform",
        "platform": host_platform,
        "controllerVisible": None,
        "canAttemptStageA": False,
        "detail": "Bluetooth host-readiness probing is currently implemented for macOS only.",
        "recommendedActions": _UNSUPPORTED_BLUETOOTH_PLATFORM_ACTIONS,
        "checks": [
            {
                "name": "platform",
                "status": "unsupported_platform",
                "evidence": host_platform or "unknown",
            }
        ],
    }


def parse_macos_bluetooth_readiness(
    *,
    stdout: str,
    stderr: str,
    exit_code: int,
) -> dict[str, object]:
    combined = f"{stdout}\n{stderr}"
    if "controllerInfo == nil" in combined or _macos_bluetooth_report_is_empty(stdout):
        return {
            "status": "not_visible",
            "platform": "Darwin",
            "controllerVisible": False,
            "canAttemptStageA": False,
            "detail": "macOS did not report a Bluetooth controller to this process.",
            "recommendedActions": _MACOS_BLUETOOTH_NOT_VISIBLE_ACTIONS,
            "checks": [
                {
                    "name": "system_profiler SPBluetoothDataType",
                    "status": "not_visible",
                    "evidence": (
                        "controllerInfo == nil"
                        if "controllerInfo == nil" in combined
                        else "empty Bluetooth report"
                    ),
                }
            ],
        }

    if exit_code == 0 and _macos_bluetooth_report_has_controller(stdout):
        return {
            "status": "ready_to_scan",
            "platform": "Darwin",
            "controllerVisible": True,
            "canAttemptStageA": True,
            "detail": "macOS reports a Bluetooth controller to this process.",
            "recommendedActions": _MACOS_BLUETOOTH_READY_ACTIONS,
            "checks": [
                {
                    "name": "system_profiler SPBluetoothDataType",
                    "status": "ready_to_scan",
                    "evidence": "Bluetooth controller fields present",
                }
            ],
        }

    return {
        "status": "unknown",
        "platform": "Darwin",
        "controllerVisible": None,
        "canAttemptStageA": False,
        "detail": "macOS Bluetooth readiness could not be determined from system_profiler.",
        "recommendedActions": _MACOS_BLUETOOTH_UNKNOWN_ACTIONS,
        "checks": [
            {
                "name": "system_profiler SPBluetoothDataType",
                "status": "unknown",
                "evidence": f"exit_code={exit_code}",
            }
        ],
    }


def plan_protocol_sanity_preflight(artifact_path: Path) -> dict[str, object]:
    stage_a_summary = inspect_stage_a_artifact(artifact_path)
    next_required_stage = _required_json_string(
        stage_a_summary,
        "nextRequiredStage",
        "print-transfer-manifest.json",
    )
    if next_required_stage != "protocol_sanity_test":
        raise HardwareTestCliError("artifact is not ready for protocol sanity test")

    try:
        with ZipFile(artifact_path) as archive:
            profile = _read_zip_json_object(archive, "profile.json")
    except BadZipFile as exc:
        raise HardwareTestCliError("artifact is not a ZIP file") from exc

    profile_id = _required_json_string(profile, "id", "profile.json")
    artifact_profile_id = _required_json_string(
        stage_a_summary,
        "profileId",
        "print-transfer-manifest.json",
    )
    if profile_id != artifact_profile_id:
        raise HardwareTestCliError("artifact profile does not match transfer manifest")

    print_config = _required_json_object(profile, "print", "profile.json")
    ble_config = _required_json_object(profile, "ble", "profile.json")
    density = _required_json_string(print_config, "defaultDensity", "profile.json.print")
    paper_mode = _required_json_string(print_config, "defaultPaperMode", "profile.json.print")
    write_characteristic = _required_json_string(
        ble_config,
        "writeCharUuid",
        "profile.json.ble",
    )
    notify_characteristics = _required_json_string_list(
        ble_config,
        "notifyCharUuids",
        "profile.json.ble",
    )

    try:
        command_plan = [
            _protocol_command(0, "wake", build_wake_command()),
            _protocol_command(1, "set_density", build_set_density_command(density)),
            _protocol_command(2, "set_paper_mode", build_set_paper_mode_command(paper_mode)),
        ]
    except ValueError as exc:
        raise HardwareTestCliError(str(exc)) from exc

    return {
        "status": "protocol_sanity_preflight_ready",
        "stage": "protocol_sanity_test",
        "deviceId": _required_json_string(
            stage_a_summary,
            "deviceId",
            "print-transfer-manifest.json",
        ),
        "profileId": profile_id,
        "writeCharacteristic": write_characteristic,
        "notifyCharacteristics": notify_characteristics,
        "density": density,
        "paperMode": paper_mode,
        "printCommandsSent": False,
        "rasterBytesIncluded": False,
        "commands": command_plan,
        "safety": {
            "requiresPhysicalPrinter": True,
            "requiresUserConfirmation": True,
            "sendsRaster": False,
            "unlocksPrinting": False,
        },
    }


def plan_tiny_visual_card_preflight(artifact_path: Path) -> dict[str, object]:
    stage_a_summary = inspect_stage_a_artifact(artifact_path)
    next_required_stage = _required_json_string(
        stage_a_summary,
        "nextRequiredStage",
        "print-transfer-manifest.json",
    )
    if next_required_stage != "protocol_sanity_test":
        raise HardwareTestCliError("artifact is not ready for tiny visual card preflight")

    try:
        with ZipFile(artifact_path) as archive:
            profile = _read_zip_json_object(archive, "profile.json")
    except BadZipFile as exc:
        raise HardwareTestCliError("artifact is not a ZIP file") from exc

    profile_id = _required_json_string(profile, "id", "profile.json")
    artifact_profile_id = _required_json_string(
        stage_a_summary,
        "profileId",
        "print-transfer-manifest.json",
    )
    if profile_id != artifact_profile_id:
        raise HardwareTestCliError("artifact profile does not match transfer manifest")

    print_config = _required_json_object(profile, "print", "profile.json")
    width_dots = _required_json_int(print_config, "widthDots", "profile.json.print")
    row_bytes = _required_json_int(print_config, "rowBytes", "profile.json.print")
    if width_dots <= 0 or width_dots % 8 != 0:
        raise HardwareTestCliError("artifact profile has invalid print width")
    if row_bytes != width_dots // 8:
        raise HardwareTestCliError("artifact profile row bytes do not match print width")

    density = _required_json_string(print_config, "defaultDensity", "profile.json.print")
    paper_mode = _required_json_string(print_config, "defaultPaperMode", "profile.json.print")
    packed_raster = _build_tiny_visual_card_raster(width_dots, TINY_VISUAL_CARD_HEIGHT_DOTS)
    try:
        raster_command = build_raster_command(
            width_dots=width_dots,
            height_dots=TINY_VISUAL_CARD_HEIGHT_DOTS,
            packed_raster=packed_raster,
        )
    except ValueError as exc:
        raise HardwareTestCliError(str(exc)) from exc

    return {
        "status": "tiny_visual_card_preflight_ready",
        "stage": "tiny_visual_test_card",
        "deviceId": _required_json_string(
            stage_a_summary,
            "deviceId",
            "print-transfer-manifest.json",
        ),
        "profileId": profile_id,
        "requiredPriorStage": "protocol_sanity_test",
        "displayText": TINY_VISUAL_CARD_TEXT,
        "widthDots": width_dots,
        "heightDots": TINY_VISUAL_CARD_HEIGHT_DOTS,
        "rowBytes": row_bytes,
        "density": density,
        "paperMode": paper_mode,
        "printCommandsSent": False,
        "rasterBytesIncluded": False,
        "plannedRaster": {
            "commandName": "raster_test_card",
            "payloadBytes": len(raster_command),
            "rasterBytes": len(packed_raster),
            "rawBytesIncluded": False,
            "contentSha256": hashlib.sha256(packed_raster).hexdigest(),
        },
        "confirmationChecklist": list(TINY_VISUAL_CARD_CONFIRMATION_CHECKLIST),
        "safety": {
            "requiresPhysicalPrinter": True,
            "requiresUserConfirmation": True,
            "requiresPriorProtocolSanity": True,
            "sendsRasterIfExecuted": True,
            "unlocksPrinting": False,
            "preflightOnly": True,
        },
    }


def build_shareable_evidence_summary(artifact_path: Path) -> dict[str, object]:
    stage_a_summary = inspect_stage_a_artifact(artifact_path)
    protocol_preflight = plan_protocol_sanity_preflight(artifact_path)
    visual_card_preflight = plan_tiny_visual_card_preflight(artifact_path)
    device_id = _required_json_string(
        stage_a_summary,
        "deviceId",
        "print-transfer-manifest.json",
    )

    return {
        "status": "shareable_stage_a_evidence_ready",
        "shareable": True,
        "artifactStatus": _required_json_string(
            stage_a_summary,
            "status",
            "print-transfer-manifest.json",
        ),
        "profileId": _required_json_string(
            stage_a_summary,
            "profileId",
            "print-transfer-manifest.json",
        ),
        "nextRequiredStage": _required_json_string(
            stage_a_summary,
            "nextRequiredStage",
            "print-transfer-manifest.json",
        ),
        "device": {
            "idRedacted": True,
            "fingerprint": f"sha256:{hashlib.sha256(device_id.encode('utf-8')).hexdigest()[:16]}",
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
                "status": _required_json_string(
                    protocol_preflight,
                    "status",
                    "protocol-sanity-preflight",
                ),
                "stage": _required_json_string(
                    protocol_preflight,
                    "stage",
                    "protocol-sanity-preflight",
                ),
                "commandCount": _json_list_length(
                    protocol_preflight,
                    "commands",
                    "protocol-sanity-preflight",
                ),
                "sendsRaster": _required_json_bool(
                    _required_json_object(
                        protocol_preflight,
                        "safety",
                        "protocol-sanity-preflight",
                    ),
                    "sendsRaster",
                    "protocol-sanity-preflight.safety",
                ),
                "unlocksPrinting": _required_json_bool(
                    _required_json_object(
                        protocol_preflight,
                        "safety",
                        "protocol-sanity-preflight",
                    ),
                    "unlocksPrinting",
                    "protocol-sanity-preflight.safety",
                ),
            },
            "tinyVisualCard": {
                "status": _required_json_string(
                    visual_card_preflight,
                    "status",
                    "tiny-visual-card-preflight",
                ),
                "stage": _required_json_string(
                    visual_card_preflight,
                    "stage",
                    "tiny-visual-card-preflight",
                ),
                "displayText": _required_json_string(
                    visual_card_preflight,
                    "displayText",
                    "tiny-visual-card-preflight",
                ),
                "heightDots": _required_json_int(
                    visual_card_preflight,
                    "heightDots",
                    "tiny-visual-card-preflight",
                ),
                "rawBytesIncluded": _required_json_bool(
                    _required_json_object(
                        visual_card_preflight,
                        "plannedRaster",
                        "tiny-visual-card-preflight",
                    ),
                    "rawBytesIncluded",
                    "tiny-visual-card-preflight.plannedRaster",
                ),
                "contentSha256": _required_json_string(
                    _required_json_object(
                        visual_card_preflight,
                        "plannedRaster",
                        "tiny-visual-card-preflight",
                    ),
                    "contentSha256",
                    "tiny-visual-card-preflight.plannedRaster",
                ),
            },
        },
    }


def _require_stage_a_artifact_files(archive: ZipFile) -> None:
    artifact_files = set(archive.namelist())
    for filename in STAGE_A_ARTIFACT_REQUIRED_FILES:
        if filename not in artifact_files:
            raise HardwareTestCliError(f"artifact missing required file: {filename}")


def _read_zip_json_object(archive: ZipFile, filename: str) -> dict[str, object]:
    try:
        decoded = json.loads(archive.read(filename).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HardwareTestCliError(f"artifact file is invalid JSON: {filename}") from exc
    if not isinstance(decoded, dict):
        raise HardwareTestCliError(f"artifact file is not a JSON object: {filename}")
    return cast(dict[str, object], decoded)


def _validate_read_only_safety(
    transfer_manifest: Mapping[str, object],
    safety_report: Mapping[str, object],
) -> None:
    if (
        transfer_manifest.get("stage") != "read_only_verification"
        or transfer_manifest.get("printCommandsSent") is not False
        or transfer_manifest.get("rasterBytesIncluded") is not False
        or safety_report.get("printingLocked") is not True
        or safety_report.get("certificationComplete") is not False
    ):
        raise HardwareTestCliError("artifact is not read-only safe")


def _macos_bluetooth_report_is_empty(stdout: str) -> bool:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    return lines == ["Bluetooth:"]


def _macos_bluetooth_report_has_controller(stdout: str) -> bool:
    report = stdout.lower()
    return (
        "bluetooth controller:" in report
        or "address:" in report
        or "state: on" in report
        or "bluetooth low energy supported: yes" in report
    )


def _required_json_string(
    value: Mapping[str, object],
    field: str,
    filename: str,
) -> str:
    field_value = value.get(field)
    if not isinstance(field_value, str) or not field_value:
        raise HardwareTestCliError(f"artifact missing required field: {filename}.{field}")
    return field_value


def _required_json_object(
    value: Mapping[str, object],
    field: str,
    filename: str,
) -> dict[str, object]:
    field_value = value.get(field)
    if not isinstance(field_value, dict):
        raise HardwareTestCliError(f"artifact missing required object: {filename}.{field}")
    return cast(dict[str, object], field_value)


def _required_json_string_list(
    value: Mapping[str, object],
    field: str,
    filename: str,
) -> list[str]:
    field_value = value.get(field)
    if not isinstance(field_value, list) or not all(
        isinstance(item, str) for item in field_value
    ):
        raise HardwareTestCliError(f"artifact missing required string list: {filename}.{field}")
    return list(field_value)


def _required_json_int(
    value: Mapping[str, object],
    field: str,
    filename: str,
) -> int:
    field_value = value.get(field)
    if not isinstance(field_value, int):
        raise HardwareTestCliError(f"artifact missing required integer: {filename}.{field}")
    return field_value


def _required_json_bool(
    value: Mapping[str, object],
    field: str,
    filename: str,
) -> bool:
    field_value = value.get(field)
    if not isinstance(field_value, bool):
        raise HardwareTestCliError(f"artifact missing required boolean: {filename}.{field}")
    return field_value


def _json_list_length(
    value: Mapping[str, object],
    field: str,
    filename: str,
) -> int:
    field_value = value.get(field)
    if not isinstance(field_value, list):
        raise HardwareTestCliError(f"artifact missing required list: {filename}.{field}")
    return len(field_value)


def _protocol_command(index: int, name: str, payload: bytes) -> dict[str, object]:
    return {
        "index": index,
        "name": name,
        "payloadBytes": len(payload),
        "hex": _hex(payload),
    }


def _build_tiny_visual_card_raster(width_dots: int, height_dots: int) -> bytes:
    row_bytes = width_dots // 8
    raster = bytearray(row_bytes * height_dots)
    _draw_text(
        raster,
        width_dots=width_dots,
        text=TINY_VISUAL_CARD_TEXT,
        x=12,
        y=18,
        scale=4,
    )

    for y in range(58, 126):
        if y % 4 in (0, 1):
            for x in range(0, 6):
                _set_raster_pixel(raster, width_dots, x, y)
            for x in range(width_dots - 6, width_dots):
                _set_raster_pixel(raster, width_dots, x, y)

    for y in range(92, 132, 8):
        for x in range(24, width_dots - 24, 16):
            block_on = ((x // 16) + (y // 8)) % 2 == 0
            if block_on:
                for block_y in range(y, min(y + 4, height_dots)):
                    for block_x in range(x, min(x + 8, width_dots)):
                        _set_raster_pixel(raster, width_dots, block_x, block_y)

    for y in (146, 147):
        for x in range(24, width_dots - 24, 4):
            _set_raster_pixel(raster, width_dots, x, y)

    return bytes(raster)


def _draw_text(
    raster: bytearray,
    *,
    width_dots: int,
    text: str,
    x: int,
    y: int,
    scale: int,
) -> None:
    cursor_x = x
    for character in text:
        glyph = _TINY_CARD_FONT[character]
        for glyph_y, row in enumerate(glyph):
            for glyph_x, enabled in enumerate(row):
                if enabled != "1":
                    continue
                for scale_y in range(scale):
                    for scale_x in range(scale):
                        _set_raster_pixel(
                            raster,
                            width_dots,
                            cursor_x + glyph_x * scale + scale_x,
                            y + glyph_y * scale + scale_y,
                        )
        cursor_x += 6 * scale


def _set_raster_pixel(raster: bytearray, width_dots: int, x: int, y: int) -> None:
    if x < 0 or x >= width_dots or y < 0:
        return
    row_bytes = width_dots // 8
    byte_index = y * row_bytes + x // 8
    if byte_index >= len(raster):
        return
    bit = 7 - (x % 8)
    raster[byte_index] |= 1 << bit


def _hex(payload: bytes) -> str:
    return " ".join(f"{byte:02x}" for byte in payload)


def urllib_transport(
    method: str,
    url: str,
    body: bytes | None,
    headers: Mapping[str, str],
    timeout: float,
) -> HttpResponse:
    request = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return HttpResponse(
                status=response.status,
                headers=_normalise_headers(response.headers),
                body=response.read(),
            )
    except urllib.error.HTTPError as exc:
        return HttpResponse(
            status=exc.code,
            headers=_normalise_headers(exc.headers),
            body=exc.read(),
        )
    except (TimeoutError, urllib.error.URLError) as exc:
        raise HardwareTestCliError(f"daemon unavailable: {exc}") from exc


def _normalise_headers(headers: object) -> dict[str, str]:
    if hasattr(headers, "items"):
        return {str(key).lower(): str(value) for key, value in headers.items()}
    return {}


def _error_detail(response: HttpResponse) -> str:
    try:
        decoded = json.loads(response.body.decode("utf-8"))
    except json.JSONDecodeError:
        return f"daemon returned HTTP {response.status}"

    if isinstance(decoded, dict) and isinstance(decoded.get("detail"), str):
        return decoded["detail"]
    return f"daemon returned HTTP {response.status}"


def _artifact_filename(headers: Mapping[str, str]) -> str:
    content_disposition = headers.get("content-disposition", "")
    for item in content_disposition.split(";"):
        part = item.strip()
        if part.lower().startswith("filename="):
            filename = part.split("=", 1)[1].strip().strip('"')
            safe_filename = Path(filename).name
            if safe_filename.endswith(".zip"):
                return safe_filename
    return "hardware-test-read-only.zip"


if __name__ == "__main__":
    main()
