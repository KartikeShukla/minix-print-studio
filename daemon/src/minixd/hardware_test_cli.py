from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO, cast
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

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

    def get_job_status(self, *, job_id: str) -> dict[str, object]:
        return self._request_json("GET", f"/v1/jobs/{urllib.parse.quote(job_id, safe='')}")

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
            if args.require_host_ready:
                _require_stage_a_host_ready(host_bluetooth_probe)
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
            if args.require_host_ready:
                _require_stage_a_host_ready(host_bluetooth_probe)
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
        if args.command == "record-protocol-sanity":
            artifact_path = record_protocol_sanity_artifact(
                stage_a_artifact_path=Path(args.stage_a_artifact),
                output_dir=Path(args.output_dir),
                confirmed_at=args.confirmed_at,
                operator_note=args.operator_note,
                no_paper_moved=args.no_paper_moved,
                no_error=args.no_error,
            )
            stdout.write(f"{artifact_path}\n")
            return 0
        if args.command == "record-tiny-visual-card":
            job_status = client.get_job_status(job_id=args.job_id)
            artifact_path = record_tiny_visual_card_artifact(
                stage_a_artifact_path=Path(args.stage_a_artifact),
                protocol_sanity_artifact_path=Path(args.protocol_sanity_artifact),
                job_status=job_status,
                output_dir=Path(args.output_dir),
            )
            stdout.write(f"{artifact_path}\n")
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
    scan_parser = subparsers.add_parser("scan", help="Scan for visible printer candidates.")
    _add_require_host_ready_argument(scan_parser)
    subparsers.add_parser(
        "host-readiness",
        help="Check whether the host exposes a Bluetooth controller for Stage A.",
    )

    export_parser = subparsers.add_parser(
        "export-read-only",
        help="Export the Stage A read-only hardware-test artifact for a device id.",
    )
    export_parser.add_argument("--device-id", required=True, help="Device id from scan output.")
    _add_require_host_ready_argument(export_parser)
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

    record_tiny_parser = subparsers.add_parser(
        "record-tiny-visual-card",
        help="Record a confirmed Stage C tiny visual card run as a hardware-test ZIP.",
    )
    record_tiny_parser.add_argument(
        "--stage-a-artifact",
        required=True,
        help="Path to the Stage A hardware-test ZIP used for this physical run.",
    )
    record_tiny_parser.add_argument(
        "--protocol-sanity-artifact",
        required=True,
        help="Path to the confirmed Stage B protocol-sanity hardware-test ZIP.",
    )
    record_tiny_parser.add_argument(
        "--job-id",
        required=True,
        help="Confirmed daemon print job id for the tiny visual card.",
    )
    record_tiny_parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for the Stage C hardware-test ZIP artifact.",
    )

    record_protocol_parser = subparsers.add_parser(
        "record-protocol-sanity",
        help="Record a confirmed Stage B protocol sanity run as a hardware-test ZIP.",
    )
    record_protocol_parser.add_argument(
        "--stage-a-artifact",
        required=True,
        help="Path to the Stage A hardware-test ZIP used for this physical run.",
    )
    record_protocol_parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for the Stage B hardware-test ZIP artifact.",
    )
    record_protocol_parser.add_argument(
        "--confirmed-at",
        required=True,
        help="UTC timestamp for the operator confirmation.",
    )
    record_protocol_parser.add_argument(
        "--operator-note",
        required=True,
        help="Operator note describing the protocol sanity run result.",
    )
    record_protocol_parser.add_argument(
        "--no-paper-moved",
        action="store_true",
        help="Confirm the protocol sanity commands did not move paper.",
    )
    record_protocol_parser.add_argument(
        "--no-error",
        action="store_true",
        help="Confirm the printer reported no fatal error during the protocol sanity run.",
    )
    return parser


def _add_require_host_ready_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--require-host-ready",
        action="store_true",
        help="Refuse Stage A daemon contact unless host Bluetooth readiness can attempt scanning.",
    )


def _require_stage_a_host_ready(host_bluetooth_probe: HostBluetoothProbe | None) -> None:
    probe_result = (host_bluetooth_probe or collect_host_bluetooth_readiness)()
    if probe_result.get("canAttemptStageA") is True:
        return

    detail = probe_result.get("detail")
    detail_text = (
        detail
        if isinstance(detail, str) and detail.strip()
        else "Host Bluetooth readiness did not allow Stage A."
    )
    action_text = _recommended_action_text(probe_result.get("recommendedActions"))
    if action_text:
        detail_text = f"{detail_text} Recommended actions: {action_text}"
    raise HardwareTestCliError(f"Stage A host readiness blocked: {detail_text}")


def _recommended_action_text(value: object) -> str:
    if not isinstance(value, list):
        return ""
    actions = [item.strip() for item in value if isinstance(item, str) and item.strip()]
    return "; ".join(actions)


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


def record_tiny_visual_card_artifact(
    *,
    stage_a_artifact_path: Path,
    protocol_sanity_artifact_path: Path,
    job_status: Mapping[str, object],
    output_dir: Path,
) -> Path:
    stage_a_summary = inspect_stage_a_artifact(stage_a_artifact_path)
    preflight = plan_tiny_visual_card_preflight(stage_a_artifact_path)
    protocol_sanity_summary = _inspect_protocol_sanity_artifact(
        artifact_path=protocol_sanity_artifact_path,
        stage_a_summary=stage_a_summary,
    )
    _validate_confirmed_tiny_visual_job(
        job_status=job_status,
        stage_a_summary=stage_a_summary,
    )

    job_id = _required_json_string(job_status, "jobId", "job-status")
    device_id = _required_json_string(stage_a_summary, "deviceId", "print-transfer-manifest.json")
    profile_id = _required_json_string(
        stage_a_summary,
        "profileId",
        "print-transfer-manifest.json",
    )
    operator_confirmation = _required_json_object(
        job_status,
        "operatorConfirmation",
        "job-status",
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / f"hardware-test-tiny-visual-card-{_safe_filename_part(job_id)}.zip"
    with ZipFile(artifact_path, "w", ZIP_DEFLATED) as archive:
        with ZipFile(stage_a_artifact_path) as stage_a_archive:
            archive.writestr("device.json", stage_a_archive.read("device.json"))
            archive.writestr("profile.json", stage_a_archive.read("profile.json"))
            archive.writestr("app-version.json", stage_a_archive.read("app-version.json"))
        archive.writestr("stage-a-summary.json", json.dumps(stage_a_summary, indent=2))
        archive.writestr(
            "protocol-sanity-summary.json",
            json.dumps(protocol_sanity_summary, indent=2),
        )
        archive.writestr("tiny-visual-card-preflight.json", json.dumps(preflight, indent=2))
        archive.writestr("job-status.json", json.dumps(dict(job_status), indent=2))
        archive.writestr(
            "print-transfer-manifest.json",
            json.dumps(
                {
                    "stage": "tiny_visual_test_card",
                    "status": "confirmed_complete",
                    "deviceId": device_id,
                    "profileId": profile_id,
                    "jobId": job_id,
                    "requiredPriorStage": "protocol_sanity_test",
                    "nextRequiredStage": "long_print_reliability",
                    "printCommandsSent": True,
                    "rasterBytesIncluded": False,
                    "operatorConfirmed": True,
                    "completionLevel": "verified",
                    "priorStageArtifactSha256": _required_json_string(
                        protocol_sanity_summary,
                        "artifactSha256",
                        "protocol-sanity-summary",
                    ),
                },
                indent=2,
            ),
        )
        archive.writestr(
            "band-manifest.json",
            json.dumps(
                {
                    "bandsSent": _required_json_int(job_status, "bandsSent", "job-status"),
                    "totalBands": _required_json_int(job_status, "totalBands", "job-status"),
                    "rowsSent": _required_json_int(job_status, "rowsSent", "job-status"),
                    "totalRows": _required_json_int(job_status, "totalRows", "job-status"),
                    "bytesSent": _required_json_int(job_status, "bytesSent", "job-status"),
                    "totalBytes": _required_json_int(job_status, "totalBytes", "job-status"),
                    "rasterBytesIncluded": False,
                },
                indent=2,
            ),
        )
        archive.writestr(
            "finalizer-result.json",
            json.dumps(
                {
                    "state": _required_json_string(job_status, "state", "job-status"),
                    "phase": _required_json_string(job_status, "phase", "job-status"),
                    "completionConfidence": _required_json_string(
                        job_status,
                        "completionConfidence",
                        "job-status",
                    ),
                },
                indent=2,
            ),
        )
        archive.writestr(
            "safety-report.json",
            json.dumps(
                {
                    "stage": "tiny_visual_test_card",
                    "printingLocked": True,
                    "certificationComplete": False,
                    "requiresLongPrintReliability": True,
                    "rasterBytesIncluded": False,
                    "unlocksPrinting": False,
                },
                indent=2,
            ),
        )
        archive.writestr(
            "user-confirmation.json",
            json.dumps(operator_confirmation, indent=2),
        )
        archive.writestr(
            "README.md",
            (
                "MiniX Print Studio Stage C tiny visual card hardware-test artifact. "
                "This archive records operator-confirmed paper output and intentionally "
                "excludes raw raster bytes.\n"
            ),
        )
    return artifact_path


def record_protocol_sanity_artifact(
    *,
    stage_a_artifact_path: Path,
    output_dir: Path,
    confirmed_at: str,
    operator_note: str,
    no_paper_moved: bool,
    no_error: bool,
) -> Path:
    if not (no_paper_moved and no_error):
        raise HardwareTestCliError(
            "protocol sanity confirmation requires no paper movement and no error"
        )

    stage_a_summary = inspect_stage_a_artifact(stage_a_artifact_path)
    preflight = plan_protocol_sanity_preflight(stage_a_artifact_path)
    device_id = _required_json_string(stage_a_summary, "deviceId", "print-transfer-manifest.json")
    profile_id = _required_json_string(
        stage_a_summary,
        "profileId",
        "print-transfer-manifest.json",
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / "hardware-test-protocol-sanity.zip"
    with ZipFile(artifact_path, "w", ZIP_DEFLATED) as archive:
        with ZipFile(stage_a_artifact_path) as stage_a_archive:
            archive.writestr("device.json", stage_a_archive.read("device.json"))
            archive.writestr("profile.json", stage_a_archive.read("profile.json"))
            archive.writestr("app-version.json", stage_a_archive.read("app-version.json"))
        archive.writestr("stage-a-summary.json", json.dumps(stage_a_summary, indent=2))
        archive.writestr("protocol-sanity-preflight.json", json.dumps(preflight, indent=2))
        archive.writestr("commands.log", _protocol_commands_log(preflight))
        archive.writestr(
            "print-transfer-manifest.json",
            json.dumps(
                {
                    "stage": "protocol_sanity_test",
                    "status": "confirmed_complete",
                    "deviceId": device_id,
                    "profileId": profile_id,
                    "requiredPriorStage": "read_only_verification",
                    "nextRequiredStage": "tiny_visual_test_card",
                    "printCommandsSent": True,
                    "rasterBytesIncluded": False,
                    "operatorConfirmed": True,
                    "completionLevel": "verified",
                },
                indent=2,
            ),
        )
        archive.writestr(
            "finalizer-result.json",
            json.dumps(
                {
                    "status": "confirmed_complete",
                    "finalOkSeen": no_error,
                    "paperMoved": not no_paper_moved,
                },
                indent=2,
            ),
        )
        archive.writestr(
            "safety-report.json",
            json.dumps(
                {
                    "stage": "protocol_sanity_test",
                    "printingLocked": True,
                    "certificationComplete": False,
                    "requiresTinyVisualCard": True,
                    "rasterBytesIncluded": False,
                    "unlocksPrinting": False,
                },
                indent=2,
            ),
        )
        archive.writestr(
            "user-confirmation.json",
            json.dumps(
                {
                    "confirmedAt": confirmed_at,
                    "noPaperMoved": no_paper_moved,
                    "noError": no_error,
                    "operatorNote": operator_note,
                    "outcome": "confirmed_complete",
                },
                indent=2,
            ),
        )
        archive.writestr(
            "README.md",
            (
                "MiniX Print Studio Stage B protocol sanity hardware-test artifact. "
                "This archive records operator-confirmed protocol command behavior and "
                "does not include raster bytes.\n"
            ),
        )
    return artifact_path


def _require_stage_a_artifact_files(archive: ZipFile) -> None:
    _require_artifact_files(
        archive,
        STAGE_A_ARTIFACT_REQUIRED_FILES,
        label="artifact",
    )


def _require_artifact_files(
    archive: ZipFile,
    required_files: Sequence[str],
    *,
    label: str,
) -> None:
    artifact_files = set(archive.namelist())
    for filename in required_files:
        if filename not in artifact_files:
            raise HardwareTestCliError(f"{label} missing required file: {filename}")


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


def _inspect_protocol_sanity_artifact(
    *,
    artifact_path: Path,
    stage_a_summary: Mapping[str, object],
) -> dict[str, object]:
    try:
        artifact_sha256 = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        with ZipFile(artifact_path) as archive:
            _require_artifact_files(
                archive,
                (
                    "print-transfer-manifest.json",
                    "safety-report.json",
                    "user-confirmation.json",
                ),
                label="protocol sanity artifact",
            )
            transfer_manifest = _read_zip_json_object(
                archive,
                "print-transfer-manifest.json",
            )
            safety_report = _read_zip_json_object(archive, "safety-report.json")
            user_confirmation = _read_zip_json_object(archive, "user-confirmation.json")
    except FileNotFoundError as exc:
        raise HardwareTestCliError("protocol sanity artifact not found") from exc
    except BadZipFile as exc:
        raise HardwareTestCliError("protocol sanity artifact is not a ZIP file") from exc

    _validate_protocol_sanity_artifact(
        transfer_manifest=transfer_manifest,
        safety_report=safety_report,
        user_confirmation=user_confirmation,
        stage_a_summary=stage_a_summary,
    )
    return {
        "stage": "protocol_sanity_test",
        "status": "confirmed_complete",
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
        "confirmedAt": _required_json_string(
            user_confirmation,
            "confirmedAt",
            "user-confirmation.json",
        ),
        "artifactSha256": artifact_sha256,
    }


def _validate_protocol_sanity_artifact(
    *,
    transfer_manifest: Mapping[str, object],
    safety_report: Mapping[str, object],
    user_confirmation: Mapping[str, object],
    stage_a_summary: Mapping[str, object],
) -> None:
    if (
        _required_json_string(transfer_manifest, "stage", "print-transfer-manifest.json")
        != "protocol_sanity_test"
    ):
        raise HardwareTestCliError("protocol sanity artifact has wrong stage")
    if (
        _required_json_string(transfer_manifest, "status", "print-transfer-manifest.json")
        != "confirmed_complete"
    ):
        raise HardwareTestCliError("protocol sanity artifact is not confirmed complete")
    if (
        _required_json_string(
            transfer_manifest,
            "nextRequiredStage",
            "print-transfer-manifest.json",
        )
        != "tiny_visual_test_card"
    ):
        raise HardwareTestCliError("protocol sanity artifact is not ready for Stage C")
    if (
        _required_json_string(transfer_manifest, "deviceId", "print-transfer-manifest.json")
        != _required_json_string(stage_a_summary, "deviceId", "print-transfer-manifest.json")
    ):
        raise HardwareTestCliError("protocol sanity artifact device does not match Stage A")
    if (
        _required_json_string(transfer_manifest, "profileId", "print-transfer-manifest.json")
        != _required_json_string(stage_a_summary, "profileId", "print-transfer-manifest.json")
    ):
        raise HardwareTestCliError("protocol sanity artifact profile does not match Stage A")
    if not _required_json_bool(
        transfer_manifest,
        "printCommandsSent",
        "print-transfer-manifest.json",
    ):
        raise HardwareTestCliError("protocol sanity artifact did not send commands")
    if _required_json_bool(
        transfer_manifest,
        "rasterBytesIncluded",
        "print-transfer-manifest.json",
    ):
        raise HardwareTestCliError("protocol sanity artifact unexpectedly includes raster bytes")
    if not _required_json_bool(
        transfer_manifest,
        "operatorConfirmed",
        "print-transfer-manifest.json",
    ):
        raise HardwareTestCliError("protocol sanity artifact lacks operator confirmation")
    if (
        _required_json_string(
            transfer_manifest,
            "completionLevel",
            "print-transfer-manifest.json",
        )
        != "verified"
    ):
        raise HardwareTestCliError("protocol sanity artifact is not verified")

    if not _required_json_bool(safety_report, "printingLocked", "safety-report.json"):
        raise HardwareTestCliError("protocol sanity artifact safety unlocked printing")
    if _required_json_bool(safety_report, "certificationComplete", "safety-report.json"):
        raise HardwareTestCliError("protocol sanity artifact prematurely completed certification")
    if _required_json_bool(safety_report, "unlocksPrinting", "safety-report.json"):
        raise HardwareTestCliError("protocol sanity artifact unlocks printing")
    if _required_json_bool(safety_report, "rasterBytesIncluded", "safety-report.json"):
        raise HardwareTestCliError("protocol sanity safety report includes raster bytes")

    if (
        _required_json_string(user_confirmation, "outcome", "user-confirmation.json")
        != "confirmed_complete"
    ):
        raise HardwareTestCliError("protocol sanity operator confirmation is incomplete")
    if not _required_json_bool(user_confirmation, "noPaperMoved", "user-confirmation.json"):
        raise HardwareTestCliError("protocol sanity operator reported paper movement")
    if not _required_json_bool(user_confirmation, "noError", "user-confirmation.json"):
        raise HardwareTestCliError("protocol sanity operator reported an error")


def _validate_confirmed_tiny_visual_job(
    *,
    job_status: Mapping[str, object],
    stage_a_summary: Mapping[str, object],
) -> None:
    if _required_json_string(job_status, "state", "job-status") != "confirmed_complete":
        raise HardwareTestCliError("tiny visual card job is not confirmed complete")
    if _required_json_string(job_status, "completionLevel", "job-status") != "verified":
        raise HardwareTestCliError("tiny visual card job is not verified")
    if (
        _required_json_string(job_status, "completionConfidence", "job-status")
        != "operator_paper_output_confirmed"
    ):
        raise HardwareTestCliError("tiny visual card job lacks operator confirmation")
    if (
        _required_json_string(job_status, "deviceId", "job-status")
        != _required_json_string(stage_a_summary, "deviceId", "print-transfer-manifest.json")
    ):
        raise HardwareTestCliError("tiny visual card job device does not match Stage A artifact")

    confirmation = _required_json_object(job_status, "operatorConfirmation", "job-status")
    if _required_json_string(confirmation, "outcome", "job-status.operatorConfirmation") != (
        "confirmed_complete"
    ):
        raise HardwareTestCliError("tiny visual card operator confirmation is incomplete")
    for field in (
        "printedTextReadable",
        "endMarkerVisible",
        "noOverheat",
        "noDisconnect",
    ):
        if not _required_json_bool(confirmation, field, "job-status.operatorConfirmation"):
            raise HardwareTestCliError("tiny visual card operator checklist did not pass")


def _safe_filename_part(value: str) -> str:
    return "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in value
    )


def _protocol_commands_log(preflight: Mapping[str, object]) -> str:
    commands = preflight.get("commands")
    if not isinstance(commands, list):
        raise HardwareTestCliError("protocol preflight missing command list")
    lines: list[str] = []
    for command in commands:
        if not isinstance(command, dict):
            raise HardwareTestCliError("protocol preflight command is invalid")
        payload_bytes = _required_json_int(
            command,
            "payloadBytes",
            "protocol-sanity-preflight.commands",
        )
        lines.append(
            f"{_required_json_int(command, 'index', 'protocol-sanity-preflight.commands')} "
            f"{_required_json_string(command, 'name', 'protocol-sanity-preflight.commands')} "
            f"payloadBytes={payload_bytes} "
            f"hex={_required_json_string(command, 'hex', 'protocol-sanity-preflight.commands')}"
        )
    return "\n".join(lines) + "\n"


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
