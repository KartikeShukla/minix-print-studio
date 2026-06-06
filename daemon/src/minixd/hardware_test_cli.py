from __future__ import annotations

import argparse
import base64
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
from datetime import UTC, datetime
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
LONG_PRINT_RELIABILITY_MIN_ROWS = 2000
LONG_PRINT_RELIABILITY_MIN_BANDS = 4
LONG_PRINT_RELIABILITY_MIN_TAIL_ROWS = 160
LONG_PRINT_RELIABILITY_HEIGHT_DOTS = 8000
LONG_PRINT_RELIABILITY_PRINT_TIMEOUT_SECONDS = 600.0
LONG_PRINT_RELIABILITY_SOURCE = "hardware-test-long-print-reliability"
LONG_PRINT_RELIABILITY_CHECKSUM = "7F3A"
LONG_PRINT_RELIABILITY_MARKERS = (
    ("START LP-TEST", 24),
    ("25% MARKER", 2000),
    ("50% MARKER", 4000),
    ("75% MARKER", 6000),
    (f"END LP-TEST {LONG_PRINT_RELIABILITY_CHECKSUM}", 7904),
)
_TINY_CARD_FONT: dict[str, tuple[str, ...]] = {
    "%": ("11001", "11010", "00100", "01000", "01011", "10011", "00000"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("10010", "10010", "10010", "11111", "00010", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
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

    def create_raster_preview(
        self,
        *,
        document_hash: str,
        render_settings_hash: str,
        profile_id: str,
        width_dots: int,
        height_dots: int,
        packed_raster: bytes,
    ) -> dict[str, object]:
        return self._request_json(
            "POST",
            "/v1/render/preview",
            body={
                "documentHash": document_hash,
                "renderSettingsHash": render_settings_hash,
                "profileId": profile_id,
                "widthDots": width_dots,
                "heightDots": height_dots,
                "rasterBase64": base64.b64encode(packed_raster).decode("ascii"),
                "safety": {
                    "allowed": True,
                    "errors": [],
                    "warnings": ["operator confirmation required"],
                },
            },
        )

    def print_preview(
        self,
        *,
        preview: Mapping[str, object],
        device_id: str,
        profile_id: str,
        paper_mode: str,
        density: str,
        timeout: float | None = None,
    ) -> dict[str, object]:
        return self._request_json(
            "POST",
            "/v1/jobs/print",
            body={
                "previewId": _required_json_string(preview, "previewId", "render-preview"),
                "approvalToken": _required_json_string(
                    preview,
                    "approvalToken",
                    "render-preview",
                ),
                "documentHash": _required_json_string(
                    preview,
                    "documentHash",
                    "render-preview",
                ),
                "renderSettingsHash": _required_json_string(
                    preview,
                    "renderSettingsHash",
                    "render-preview",
                ),
                "profileId": profile_id,
                "paperMode": paper_mode,
                "density": density,
                "copies": 1,
                "source": LONG_PRINT_RELIABILITY_SOURCE,
                "deviceId": device_id,
            },
            timeout=timeout,
        )

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
        timeout: float | None = None,
    ) -> dict[str, object]:
        response = self._request(method, path, body=body, timeout=timeout)
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
        timeout: float | None = None,
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
            timeout if timeout is not None else self._timeout,
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
        token=os.environ.get("MINIX_DAEMON_TOKEN", ""),
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
            client.export_read_only_artifact(
                device_id=args.device_id,
                output_dir=Path(args.output_dir),
            )
            stdout.write("artifact-exported\n")
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
        if args.command == "inspect-trusted-printer-record":
            inspect_trusted_printer_record(Path(args.record_path))
            stdout.write("trusted-printer-record-inspected\n")
            return 0
        if args.command == "inspect-stable-support-gate":
            inspect_stable_support_gate(Path(args.record_path))
            stdout.write("stable-support-gate-inspected\n")
            return 0
        if args.command == "inspect-agent-direct-policy-review":
            inspect_agent_direct_policy_review(Path(args.record_path))
            stdout.write("agent-direct-policy-review-inspected\n")
            return 0
        if args.command == "record-agent-direct-policy-review":
            record_agent_direct_policy_review(
                stable_support_gate_path=Path(args.stable_support_gate),
                output_dir=Path(args.output_dir),
            )
            stdout.write("agent-direct-policy-review-recorded\n")
            return 0
        if args.command == "record-protocol-sanity":
            record_protocol_sanity_artifact(
                stage_a_artifact_path=Path(args.stage_a_artifact),
                output_dir=Path(args.output_dir),
                confirmed_at=args.confirmed_at,
                operator_note=args.operator_note,
                no_paper_moved=args.no_paper_moved,
                no_error=args.no_error,
            )
            stdout.write("protocol-sanity-recorded\n")
            return 0
        if args.command == "record-tiny-visual-card":
            job_status = client.get_job_status(job_id=args.job_id)
            record_tiny_visual_card_artifact(
                stage_a_artifact_path=Path(args.stage_a_artifact),
                protocol_sanity_artifact_path=Path(args.protocol_sanity_artifact),
                job_status=job_status,
                output_dir=Path(args.output_dir),
            )
            stdout.write("tiny-visual-card-recorded\n")
            return 0
        if args.command == "record-trusted-printer":
            record_trusted_printer(
                stage_a_artifact_path=Path(args.stage_a_artifact),
                protocol_sanity_artifact_path=Path(args.protocol_sanity_artifact),
                tiny_visual_card_artifact_path=Path(args.tiny_visual_card_artifact),
                output_dir=Path(args.output_dir),
            )
            stdout.write("trusted-printer-recorded\n")
            return 0
        if args.command == "record-long-print-reliability":
            job_status = client.get_job_status(job_id=args.job_id)
            record_long_print_reliability_artifact(
                stage_a_artifact_path=Path(args.stage_a_artifact),
                protocol_sanity_artifact_path=Path(args.protocol_sanity_artifact),
                tiny_visual_card_artifact_path=Path(args.tiny_visual_card_artifact),
                trusted_printer_record_path=Path(args.trusted_printer_record),
                job_status=job_status,
                output_dir=Path(args.output_dir),
            )
            stdout.write("long-print-reliability-recorded\n")
            return 0
        if args.command == "record-stable-support-gate":
            record_stable_support_gate(
                stage_a_artifact_path=Path(args.stage_a_artifact),
                protocol_sanity_artifact_path=Path(args.protocol_sanity_artifact),
                tiny_visual_card_artifact_path=Path(args.tiny_visual_card_artifact),
                trusted_printer_record_path=Path(args.trusted_printer_record),
                long_print_reliability_artifact_path=Path(
                    args.long_print_reliability_artifact
                ),
                output_dir=Path(args.output_dir),
            )
            stdout.write("stable-support-gate-recorded\n")
            return 0
        if args.command == "print-long-print-reliability":
            print_long_print_reliability_fixture(
                client=client,
                stage_a_artifact_path=Path(args.stage_a_artifact),
                protocol_sanity_artifact_path=Path(args.protocol_sanity_artifact),
                tiny_visual_card_artifact_path=Path(args.tiny_visual_card_artifact),
                trusted_printer_record_path=Path(args.trusted_printer_record),
            )
            stdout.write("long-print-reliability-print-started\n")
            return 0
    except HardwareTestCliError as exc:
        stderr.write(f"{exc}\n")
        return 2

    stderr.write("unsupported command\n")
    return 2


def main() -> None:
    raise SystemExit(run())


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="minix-hardware-test",
        description=(
            "Run MiniX Print Studio hardware validation helpers against a local daemon. "
            "Daemon bearer tokens are read from MINIX_DAEMON_TOKEN."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MINIX_DAEMON_BASE_URL", "http://127.0.0.1:39281"),
        help="Daemon base URL. Defaults to MINIX_DAEMON_BASE_URL or localhost.",
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

    trusted_inspect_parser = subparsers.add_parser(
        "inspect-trusted-printer-record",
        help="Inspect a trusted-printer JSON record without contacting the daemon.",
    )
    trusted_inspect_parser.add_argument(
        "record_path",
        help="Path to a trusted-printer JSON record.",
    )
    stable_support_inspect_parser = subparsers.add_parser(
        "inspect-stable-support-gate",
        help="Inspect a stable-support gate JSON record without contacting the daemon.",
    )
    stable_support_inspect_parser.add_argument(
        "record_path",
        help="Path to a stable-support gate JSON record.",
    )
    agent_rules_inspect_parser = subparsers.add_parser(
        "inspect-agent-direct-policy-review",
        help="Inspect an agent-direct policy-review JSON record without contacting the daemon.",
    )
    agent_rules_inspect_parser.add_argument(
        "record_path",
        help="Path to an agent-direct policy-review JSON record.",
    )
    agent_rules_parser = subparsers.add_parser(
        "record-agent-direct-policy-review",
        help=(
            "Record an agent-direct printing policy-review gate from a "
            "stable-support gate without enabling direct printing."
        ),
    )
    agent_rules_parser.add_argument(
        "--stable-support-gate",
        required=True,
        help="Path to the stable-support gate JSON record.",
    )
    agent_rules_parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for the agent-direct policy-review JSON record.",
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

    record_trusted_parser = subparsers.add_parser(
        "record-trusted-printer",
        help="Record a local trusted-printer JSON record from reviewed Stage A/B/C artifacts.",
    )
    record_trusted_parser.add_argument(
        "--stage-a-artifact",
        required=True,
        help="Path to the Stage A hardware-test ZIP for the printer.",
    )
    record_trusted_parser.add_argument(
        "--protocol-sanity-artifact",
        required=True,
        help="Path to the confirmed Stage B protocol-sanity hardware-test ZIP.",
    )
    record_trusted_parser.add_argument(
        "--tiny-visual-card-artifact",
        required=True,
        help="Path to the confirmed Stage C tiny visual-card hardware-test ZIP.",
    )
    record_trusted_parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for the trusted-printer JSON record.",
    )

    record_long_print_parser = subparsers.add_parser(
        "record-long-print-reliability",
        help="Record a confirmed Stage D long-print reliability run as a hardware-test ZIP.",
    )
    record_long_print_parser.add_argument(
        "--stage-a-artifact",
        required=True,
        help="Path to the Stage A hardware-test ZIP for the printer.",
    )
    record_long_print_parser.add_argument(
        "--protocol-sanity-artifact",
        required=True,
        help="Path to the confirmed Stage B protocol-sanity hardware-test ZIP.",
    )
    record_long_print_parser.add_argument(
        "--tiny-visual-card-artifact",
        required=True,
        help="Path to the confirmed Stage C tiny visual-card hardware-test ZIP.",
    )
    record_long_print_parser.add_argument(
        "--trusted-printer-record",
        required=True,
        help="Path to the local trusted-printer JSON record.",
    )
    record_long_print_parser.add_argument(
        "--job-id",
        required=True,
        help="Confirmed daemon print job id for the long-print reliability run.",
    )
    record_long_print_parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for the Stage D hardware-test ZIP artifact.",
    )

    record_stable_support_parser = subparsers.add_parser(
        "record-stable-support-gate",
        help=(
            "Record reviewed Stage D evidence that enables stable support claims "
            "without enabling agent direct printing."
        ),
    )
    record_stable_support_parser.add_argument(
        "--stage-a-artifact",
        required=True,
        help="Path to the Stage A hardware-test ZIP for the printer.",
    )
    record_stable_support_parser.add_argument(
        "--protocol-sanity-artifact",
        required=True,
        help="Path to the confirmed Stage B protocol-sanity hardware-test ZIP.",
    )
    record_stable_support_parser.add_argument(
        "--tiny-visual-card-artifact",
        required=True,
        help="Path to the confirmed Stage C tiny visual-card hardware-test ZIP.",
    )
    record_stable_support_parser.add_argument(
        "--trusted-printer-record",
        required=True,
        help="Path to the local trusted-printer JSON record.",
    )
    record_stable_support_parser.add_argument(
        "--long-print-reliability-artifact",
        required=True,
        help="Path to the confirmed Stage D long-print reliability ZIP.",
    )
    record_stable_support_parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for the stable-support gate JSON record.",
    )

    print_long_print_parser = subparsers.add_parser(
        "print-long-print-reliability",
        help="Print the Stage D long-print reliability marker fixture through the daemon.",
    )
    print_long_print_parser.add_argument(
        "--stage-a-artifact",
        required=True,
        help="Path to the Stage A hardware-test ZIP for the printer.",
    )
    print_long_print_parser.add_argument(
        "--protocol-sanity-artifact",
        required=True,
        help="Path to the confirmed Stage B protocol-sanity hardware-test ZIP.",
    )
    print_long_print_parser.add_argument(
        "--tiny-visual-card-artifact",
        required=True,
        help="Path to the confirmed Stage C tiny visual-card hardware-test ZIP.",
    )
    print_long_print_parser.add_argument(
        "--trusted-printer-record",
        required=True,
        help="Path to the local trusted-printer JSON record.",
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
            "fingerprint": _device_fingerprint(device_id),
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


def record_trusted_printer(
    *,
    stage_a_artifact_path: Path,
    protocol_sanity_artifact_path: Path,
    tiny_visual_card_artifact_path: Path,
    output_dir: Path,
) -> Path:
    stage_a_summary = inspect_stage_a_artifact(stage_a_artifact_path)
    protocol_sanity_summary = _inspect_protocol_sanity_artifact(
        artifact_path=protocol_sanity_artifact_path,
        stage_a_summary=stage_a_summary,
    )
    tiny_visual_card_summary = _inspect_tiny_visual_card_artifact(
        artifact_path=tiny_visual_card_artifact_path,
        stage_a_summary=stage_a_summary,
        protocol_sanity_summary=protocol_sanity_summary,
    )
    device_id = _required_json_string(stage_a_summary, "deviceId", "print-transfer-manifest.json")
    profile_id = _required_json_string(
        stage_a_summary,
        "profileId",
        "print-transfer-manifest.json",
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    device_fingerprint = _device_fingerprint(device_id)
    record_path = output_dir / f"trusted-printer-{device_fingerprint.removeprefix('sha256:')}.json"
    record = {
        "schemaVersion": 1,
        "status": "trusted_for_manual_continuous_printing",
        "device": {
            "idRedacted": True,
            "fingerprint": device_fingerprint,
        },
        "profileId": profile_id,
        "trustedAt": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "operatorNoteIncluded": False,
        "trustedFor": ["manual_continuous_printing"],
        "hardwareEvidence": {
            "stageA": {
                "stage": "read_only_verification",
                "status": _required_json_string(
                    stage_a_summary,
                    "status",
                    "print-transfer-manifest.json",
                ),
                "artifactSha256": hashlib.sha256(stage_a_artifact_path.read_bytes()).hexdigest(),
            },
            "protocolSanity": {
                "stage": "protocol_sanity_test",
                "status": _required_json_string(
                    protocol_sanity_summary,
                    "status",
                    "protocol-sanity-summary",
                ),
                "artifactSha256": _required_json_string(
                    protocol_sanity_summary,
                    "artifactSha256",
                    "protocol-sanity-summary",
                ),
            },
            "tinyVisualCard": {
                "stage": "tiny_visual_test_card",
                "status": _required_json_string(
                    tiny_visual_card_summary,
                    "status",
                    "tiny-visual-card-summary",
                ),
                "jobId": _required_json_string(
                    tiny_visual_card_summary,
                    "jobId",
                    "tiny-visual-card-summary",
                ),
                "artifactSha256": _required_json_string(
                    tiny_visual_card_summary,
                    "artifactSha256",
                    "tiny-visual-card-summary",
                ),
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
    record_path.write_text(f"{json.dumps(record, indent=2)}\n", encoding="utf-8")
    return record_path


def inspect_trusted_printer_record(record_path: Path) -> dict[str, object]:
    try:
        decoded = json.loads(record_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HardwareTestCliError("trusted-printer record not found") from exc
    except json.JSONDecodeError as exc:
        raise HardwareTestCliError("trusted-printer record is invalid JSON") from exc
    if not isinstance(decoded, dict):
        raise HardwareTestCliError("trusted-printer record is not a JSON object")
    if "deviceId" in decoded or "rawDeviceId" in decoded:
        raise HardwareTestCliError("trusted-printer record exposes raw device id")

    device = _required_json_object(decoded, "device", "trusted-printer-record")
    safety = _required_json_object(decoded, "safety", "trusted-printer-record")
    hardware_evidence = _required_json_object(
        decoded,
        "hardwareEvidence",
        "trusted-printer-record",
    )
    if "deviceId" in device or "rawDeviceId" in device:
        raise HardwareTestCliError("trusted-printer record exposes raw device id")
    if _required_json_string(decoded, "status", "trusted-printer-record") != (
        "trusted_for_manual_continuous_printing"
    ):
        raise HardwareTestCliError("trusted-printer record has wrong status")
    if not _required_json_bool(device, "idRedacted", "trusted-printer-record.device"):
        raise HardwareTestCliError("trusted-printer record exposes raw device id")
    device_fingerprint = _required_json_string(
        device,
        "fingerprint",
        "trusted-printer-record.device",
    )
    if not device_fingerprint.startswith("sha256:"):
        raise HardwareTestCliError("trusted-printer record has invalid device fingerprint")
    trusted_for = _required_json_string_list(decoded, "trustedFor", "trusted-printer-record")
    if "manual_continuous_printing" not in trusted_for:
        raise HardwareTestCliError("trusted-printer record does not trust manual printing")
    operator_note_included = _required_json_bool(
        decoded,
        "operatorNoteIncluded",
        "trusted-printer-record",
    )
    if operator_note_included:
        raise HardwareTestCliError("trusted-printer record includes operator free text")
    if not _required_json_bool(
        safety,
        "manualContinuousPrintingEnabled",
        "trusted-printer-record.safety",
    ):
        raise HardwareTestCliError("trusted-printer record does not enable manual printing")
    if not _required_json_bool(
        safety,
        "longPrintReliabilityRequired",
        "trusted-printer-record.safety",
    ):
        raise HardwareTestCliError("trusted-printer record skips long-print reliability")
    for field in (
        "longPrintPrintingEnabled",
        "agentDirectPrintingEnabled",
        "stableSupportClaimEnabled",
    ):
        if _required_json_bool(safety, field, "trusted-printer-record.safety"):
            raise HardwareTestCliError("trusted-printer record unlocks later-stage support")
    next_required_stage = _required_json_string(
        decoded,
        "nextRequiredStage",
        "trusted-printer-record",
    )
    if next_required_stage != "long_print_reliability":
        raise HardwareTestCliError("trusted-printer record has wrong next stage")

    return {
        "status": "trusted_for_manual_continuous_printing",
        "profileId": _required_json_string(decoded, "profileId", "trusted-printer-record"),
        "device": {
            "idRedacted": True,
            "fingerprint": device_fingerprint,
        },
        "trustedFor": trusted_for,
        "operatorNoteIncluded": False,
        "hardwareEvidence": {
            "stageA": _summarize_trusted_record_evidence_stage(
                hardware_evidence,
                "stageA",
                expected_stage="read_only_verification",
            ),
            "protocolSanity": _summarize_trusted_record_evidence_stage(
                hardware_evidence,
                "protocolSanity",
                expected_stage="protocol_sanity_test",
            ),
            "tinyVisualCard": _summarize_trusted_record_evidence_stage(
                hardware_evidence,
                "tinyVisualCard",
                expected_stage="tiny_visual_test_card",
            ),
        },
        "safety": {
            "manualContinuousPrintingEnabled": True,
            "longPrintReliabilityRequired": True,
            "longPrintPrintingEnabled": False,
            "agentDirectPrintingEnabled": False,
            "stableSupportClaimEnabled": False,
        },
        "nextRequiredStage": next_required_stage,
    }


def inspect_stable_support_gate(record_path: Path) -> dict[str, object]:
    try:
        decoded = json.loads(record_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HardwareTestCliError("stable-support gate not found") from exc
    except json.JSONDecodeError as exc:
        raise HardwareTestCliError("stable-support gate is invalid JSON") from exc
    if not isinstance(decoded, dict):
        raise HardwareTestCliError("stable-support gate is not a JSON object")
    if "deviceId" in decoded or "rawDeviceId" in decoded:
        raise HardwareTestCliError("stable-support gate exposes raw device id")

    device = _required_json_object(decoded, "device", "stable-support-gate")
    safety = _required_json_object(decoded, "safety", "stable-support-gate")
    hardware_evidence = _required_json_object(
        decoded,
        "hardwareEvidence",
        "stable-support-gate",
    )
    if "deviceId" in device or "rawDeviceId" in device:
        raise HardwareTestCliError("stable-support gate exposes raw device id")
    if (
        _required_json_string(decoded, "status", "stable-support-gate")
        != "stable_support_claims_enabled"
    ):
        raise HardwareTestCliError("stable-support gate has wrong status")
    if not _required_json_bool(device, "idRedacted", "stable-support-gate.device"):
        raise HardwareTestCliError("stable-support gate exposes raw device id")
    device_fingerprint = _required_json_string(
        device,
        "fingerprint",
        "stable-support-gate.device",
    )
    if not device_fingerprint.startswith("sha256:"):
        raise HardwareTestCliError("stable-support gate has invalid device fingerprint")
    trusted_for = _required_json_string_list(decoded, "trustedFor", "stable-support-gate")
    for trust in (
        "manual_continuous_printing",
        "long_print_continuous_printing",
        "stable_support_claims",
    ):
        if trust not in trusted_for:
            raise HardwareTestCliError("stable-support gate does not include required trust")
    if _required_json_bool(decoded, "operatorNoteIncluded", "stable-support-gate"):
        raise HardwareTestCliError("stable-support gate includes operator free text")
    if _required_json_bool(decoded, "rasterBytesIncluded", "stable-support-gate"):
        raise HardwareTestCliError("stable-support gate includes raster bytes")

    for field in (
        "manualContinuousPrintingEnabled",
        "longPrintReliabilityPassed",
        "longPrintPrintingEnabled",
        "stableSupportClaimEnabled",
    ):
        if not _required_json_bool(safety, field, "stable-support-gate.safety"):
            raise HardwareTestCliError("stable-support gate is missing enabled support")
    if _required_json_bool(
        safety,
        "agentDirectPrintingEnabled",
        "stable-support-gate.safety",
    ):
        raise HardwareTestCliError("stable-support gate enables agent direct printing")
    if (
        _required_json_string(
            safety,
            "agentDirectPrintingDefault",
            "stable-support-gate.safety",
        )
        != "approval_required"
    ):
        raise HardwareTestCliError("stable-support gate has wrong agent direct default")
    next_required_stage = _required_json_string(
        decoded,
        "nextRequiredStage",
        "stable-support-gate",
    )
    if next_required_stage != "agent_direct_printing_policy_review":
        raise HardwareTestCliError("stable-support gate has wrong next stage")

    return {
        "status": "stable_support_claims_enabled",
        "profileId": _required_json_string(decoded, "profileId", "stable-support-gate"),
        "device": {
            "idRedacted": True,
            "fingerprint": device_fingerprint,
        },
        "trustedFor": trusted_for,
        "operatorNoteIncluded": False,
        "rasterBytesIncluded": False,
        "hardwareEvidence": {
            "stageA": _summarize_support_gate_evidence_stage(
                hardware_evidence,
                "stageA",
                expected_stage="read_only_verification",
            ),
            "protocolSanity": _summarize_support_gate_evidence_stage(
                hardware_evidence,
                "protocolSanity",
                expected_stage="protocol_sanity_test",
            ),
            "tinyVisualCard": _summarize_support_gate_evidence_stage(
                hardware_evidence,
                "tinyVisualCard",
                expected_stage="tiny_visual_test_card",
            ),
            "trustedPrinter": _summarize_support_gate_evidence_stage(
                hardware_evidence,
                "trustedPrinter",
                expected_stage="trusted_printer_record",
            ),
            "longPrintReliability": _summarize_support_gate_evidence_stage(
                hardware_evidence,
                "longPrintReliability",
                expected_stage="long_print_reliability",
            ),
        },
        "safety": {
            "manualContinuousPrintingEnabled": True,
            "longPrintReliabilityPassed": True,
            "longPrintPrintingEnabled": True,
            "stableSupportClaimEnabled": True,
            "agentDirectPrintingEnabled": False,
            "agentDirectPrintingDefault": "approval_required",
        },
        "nextRequiredStage": next_required_stage,
    }


def _summarize_support_gate_evidence_stage(
    hardware_evidence: Mapping[str, object],
    field: str,
    *,
    expected_stage: str,
) -> dict[str, object]:
    evidence = _required_json_object(
        hardware_evidence,
        field,
        "stable-support-gate.hardwareEvidence",
    )
    stage = _required_json_string(
        evidence,
        "stage",
        f"stable-support-gate.hardwareEvidence.{field}",
    )
    if stage != expected_stage:
        raise HardwareTestCliError("stable-support gate evidence stage mismatch")
    artifact_sha256 = _required_json_string(
        evidence,
        "artifactSha256",
        f"stable-support-gate.hardwareEvidence.{field}",
    )
    if len(artifact_sha256) != 64:
        raise HardwareTestCliError("stable-support gate evidence digest is invalid")
    return {
        "stage": stage,
        "status": _required_json_string(
            evidence,
            "status",
            f"stable-support-gate.hardwareEvidence.{field}",
        ),
        "artifactSha256Included": True,
    }


def record_agent_direct_policy_review(
    *,
    stable_support_gate_path: Path,
    output_dir: Path,
) -> Path:
    stable_support_summary = inspect_stable_support_gate(stable_support_gate_path)
    safety = _required_json_object(
        stable_support_summary,
        "safety",
        "stable-support-gate",
    )
    if (
        _required_json_string(
            stable_support_summary,
            "status",
            "stable-support-gate",
        )
        != "stable_support_claims_enabled"
    ):
        raise HardwareTestCliError("stable-support gate has wrong status")
    for field in ("stableSupportClaimEnabled", "longPrintPrintingEnabled"):
        if not _required_json_bool(safety, field, "stable-support-gate.safety"):
            raise HardwareTestCliError("stable-support gate does not enable stable support")
    output_dir.mkdir(parents=True, exist_ok=True)
    record_path = output_dir / "agent-direct-policy-review.json"
    record = {
        "schemaVersion": 1,
        "status": "agent_direct_policy_reviewed",
        "sourceGate": {
            "stage": "stable_support_gate",
            "status": "stable_support_claims_enabled",
            "localRecordValidated": True,
        },
        "agentRules": {
            "directPrintEnabled": False,
            "directPrintDefault": "disabled",
            "approvalRequiredByDefault": True,
            "longDirectPrintRequiresApproval": True,
            "overLimitBehavior": "preview_and_ask",
            "noAutomaticRetryAfterPrintableBytes": True,
            "rawBleWritesAllowed": False,
            "unsafeResumeAllowed": False,
            "requiresTrustedPrinter": True,
            "requiresStableSupportGate": True,
        },
        "limits": {
            "maxHeightDots": 1000,
            "warnTotalBlackCoverage": 0.30,
            "blockTotalBlackCoverage": 0.45,
            "blockBandCoverage": 0.70,
            "maxCopies": 1,
            "jobsPerMinute": 3,
        },
        "safety": {
            "stableSupportClaimEnabled": True,
            "longPrintPrintingEnabled": True,
            "agentDirectPrintingEnabled": False,
            "agentDirectPrintingDefault": "approval_required",
        },
        "nextRequiredStage": "explicit_user_opt_in_for_agent_direct_printing",
    }
    record_path.write_text(f"{json.dumps(record, indent=2)}\n", encoding="utf-8")
    return record_path


def inspect_agent_direct_policy_review(record_path: Path) -> dict[str, object]:
    try:
        decoded = json.loads(record_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HardwareTestCliError("agent-direct policy review not found") from exc
    except json.JSONDecodeError as exc:
        raise HardwareTestCliError("agent-direct policy review is invalid JSON") from exc
    if not isinstance(decoded, dict):
        raise HardwareTestCliError("agent-direct policy review is not a JSON object")
    if (
        "deviceId" in decoded
        or "rawDeviceId" in decoded
        or "device" in decoded
        or "profileId" in decoded
        or "deviceFingerprint" in decoded
        or "fingerprint" in decoded
    ):
        raise HardwareTestCliError("agent-direct policy review exposes raw device id")

    source_gate = _required_json_object(
        decoded,
        "sourceGate",
        "agent-direct-policy-review",
    )
    agent_rules = _required_json_object(
        decoded,
        "agentRules",
        "agent-direct-policy-review",
    )
    limits = _required_json_object(decoded, "limits", "agent-direct-policy-review")
    safety = _required_json_object(decoded, "safety", "agent-direct-policy-review")
    if (
        _required_json_string(decoded, "status", "agent-direct-policy-review")
        != "agent_direct_policy_reviewed"
    ):
        raise HardwareTestCliError("agent-direct policy review has wrong status")
    if (
        _required_json_string(source_gate, "stage", "agent-direct-policy-review.sourceGate")
        != "stable_support_gate"
    ):
        raise HardwareTestCliError("agent-direct policy review has wrong source gate")
    if (
        _required_json_string(source_gate, "status", "agent-direct-policy-review.sourceGate")
        != "stable_support_claims_enabled"
    ):
        raise HardwareTestCliError("agent-direct policy review has wrong source status")
    if not _required_json_bool(
        source_gate,
        "localRecordValidated",
        "agent-direct-policy-review.sourceGate",
    ):
        raise HardwareTestCliError("agent-direct policy review source is not validated")

    for field in (
        "approvalRequiredByDefault",
        "longDirectPrintRequiresApproval",
        "noAutomaticRetryAfterPrintableBytes",
        "requiresTrustedPrinter",
        "requiresStableSupportGate",
    ):
        if not _required_json_bool(agent_rules, field, "agent-direct-policy-review.agentRules"):
            raise HardwareTestCliError("agent-direct policy review weakens approval policy")
    for field in ("directPrintEnabled", "rawBleWritesAllowed", "unsafeResumeAllowed"):
        if _required_json_bool(agent_rules, field, "agent-direct-policy-review.agentRules"):
            raise HardwareTestCliError("agent-direct policy review enables unsafe direct printing")
    if (
        _required_json_string(
            agent_rules,
            "directPrintDefault",
            "agent-direct-policy-review.agentRules",
        )
        != "disabled"
    ):
        raise HardwareTestCliError("agent-direct policy review has wrong direct default")
    if (
        _required_json_string(
            agent_rules,
            "overLimitBehavior",
            "agent-direct-policy-review.agentRules",
        )
        != "preview_and_ask"
    ):
        raise HardwareTestCliError("agent-direct policy review has wrong over-limit behavior")

    expected_limits = {
        "maxHeightDots": 1000,
        "warnTotalBlackCoverage": 0.30,
        "blockTotalBlackCoverage": 0.45,
        "blockBandCoverage": 0.70,
        "maxCopies": 1,
        "jobsPerMinute": 3,
    }
    for field, expected in expected_limits.items():
        if _required_json_number(limits, field, "agent-direct-policy-review.limits") != expected:
            raise HardwareTestCliError("agent-direct policy review has wrong safety limits")

    for field in ("stableSupportClaimEnabled", "longPrintPrintingEnabled"):
        if not _required_json_bool(safety, field, "agent-direct-policy-review.safety"):
            raise HardwareTestCliError("agent-direct policy review lacks stable support")
    if _required_json_bool(
        safety,
        "agentDirectPrintingEnabled",
        "agent-direct-policy-review.safety",
    ):
        raise HardwareTestCliError("agent-direct policy review enables direct printing")
    if (
        _required_json_string(
            safety,
            "agentDirectPrintingDefault",
            "agent-direct-policy-review.safety",
        )
        != "approval_required"
    ):
        raise HardwareTestCliError("agent-direct policy review has wrong approval default")
    next_required_stage = _required_json_string(
        decoded,
        "nextRequiredStage",
        "agent-direct-policy-review",
    )
    if next_required_stage != "explicit_user_opt_in_for_agent_direct_printing":
        raise HardwareTestCliError("agent-direct policy review has wrong next stage")

    return {
        "status": "agent_direct_policy_reviewed",
        "sourceGate": {
            "stage": "stable_support_gate",
            "status": "stable_support_claims_enabled",
            "localRecordValidated": True,
        },
        "agentRules": {
            "directPrintEnabled": False,
            "directPrintDefault": "disabled",
            "approvalRequiredByDefault": True,
            "longDirectPrintRequiresApproval": True,
            "overLimitBehavior": "preview_and_ask",
            "noAutomaticRetryAfterPrintableBytes": True,
            "rawBleWritesAllowed": False,
            "unsafeResumeAllowed": False,
            "requiresTrustedPrinter": True,
            "requiresStableSupportGate": True,
        },
        "limits": expected_limits,
        "safety": {
            "stableSupportClaimEnabled": True,
            "longPrintPrintingEnabled": True,
            "agentDirectPrintingEnabled": False,
            "agentDirectPrintingDefault": "approval_required",
        },
        "nextRequiredStage": next_required_stage,
    }


def _summarize_trusted_record_evidence_stage(
    hardware_evidence: Mapping[str, object],
    field: str,
    *,
    expected_stage: str,
) -> dict[str, object]:
    evidence = _required_json_object(
        hardware_evidence,
        field,
        "trusted-printer-record.hardwareEvidence",
    )
    stage = _required_json_string(
        evidence,
        "stage",
        f"trusted-printer-record.hardwareEvidence.{field}",
    )
    if stage != expected_stage:
        raise HardwareTestCliError("trusted-printer record evidence stage mismatch")
    artifact_sha256 = _required_json_string(
        evidence,
        "artifactSha256",
        f"trusted-printer-record.hardwareEvidence.{field}",
    )
    if len(artifact_sha256) != 64:
        raise HardwareTestCliError("trusted-printer record evidence digest is invalid")
    return {
        "stage": stage,
        "status": _required_json_string(
            evidence,
            "status",
            f"trusted-printer-record.hardwareEvidence.{field}",
        ),
        "artifactSha256Included": True,
    }


def print_long_print_reliability_fixture(
    *,
    client: HardwareTestClient,
    stage_a_artifact_path: Path,
    protocol_sanity_artifact_path: Path,
    tiny_visual_card_artifact_path: Path,
    trusted_printer_record_path: Path,
) -> dict[str, object]:
    stage_a_summary = inspect_stage_a_artifact(stage_a_artifact_path)
    trusted_printer_summary = _inspect_trusted_printer_record(
        record_path=trusted_printer_record_path,
        stage_a_artifact_path=stage_a_artifact_path,
        protocol_sanity_artifact_path=protocol_sanity_artifact_path,
        tiny_visual_card_artifact_path=tiny_visual_card_artifact_path,
        stage_a_summary=stage_a_summary,
    )
    profile = _read_stage_a_profile(stage_a_artifact_path)
    profile_id = _required_json_string(profile, "id", "profile.json")
    stage_profile_id = _required_json_string(
        stage_a_summary,
        "profileId",
        "print-transfer-manifest.json",
    )
    if profile_id != stage_profile_id:
        raise HardwareTestCliError("artifact profile does not match transfer manifest")

    print_config = _required_json_object(profile, "print", "profile.json")
    width_dots = _required_json_int(print_config, "widthDots", "profile.json.print")
    row_bytes = _required_json_int(print_config, "rowBytes", "profile.json.print")
    if width_dots <= 0 or width_dots % 8 != 0:
        raise HardwareTestCliError("artifact profile has invalid print width")
    if row_bytes != width_dots // 8:
        raise HardwareTestCliError("artifact profile row bytes do not match print width")
    paper_mode = _required_json_string(print_config, "defaultPaperMode", "profile.json.print")
    density = _required_json_string(print_config, "defaultDensity", "profile.json.print")
    if paper_mode != "continuous":
        raise HardwareTestCliError("long-print reliability requires continuous paper mode")

    device_id = _required_json_string(
        stage_a_summary,
        "deviceId",
        "print-transfer-manifest.json",
    )
    packed_raster = _build_long_print_reliability_raster(
        width_dots=width_dots,
        height_dots=LONG_PRINT_RELIABILITY_HEIGHT_DOTS,
    )
    raster_sha = _sha256_hex(packed_raster)
    document_hash = _stable_json_sha256(
        {
            "source": LONG_PRINT_RELIABILITY_SOURCE,
            "profileId": profile_id,
            "widthDots": width_dots,
            "heightDots": LONG_PRINT_RELIABILITY_HEIGHT_DOTS,
            "rasterSha256": raster_sha,
            "markers": [
                {"text": text, "row": row}
                for text, row in LONG_PRINT_RELIABILITY_MARKERS
            ],
        }
    )
    render_settings_hash = _stable_json_sha256(
        {
            "source": LONG_PRINT_RELIABILITY_SOURCE,
            "paperMode": paper_mode,
            "density": density,
        }
    )
    preview = client.create_raster_preview(
        document_hash=document_hash,
        render_settings_hash=render_settings_hash,
        profile_id=profile_id,
        width_dots=width_dots,
        height_dots=LONG_PRINT_RELIABILITY_HEIGHT_DOTS,
        packed_raster=packed_raster,
    )
    job_status = client.print_preview(
        preview=preview,
        device_id=device_id,
        profile_id=profile_id,
        paper_mode=paper_mode,
        density=density,
        timeout=LONG_PRINT_RELIABILITY_PRINT_TIMEOUT_SECONDS,
    )
    _validate_started_long_print_job(
        job_status=job_status,
        stage_a_summary=stage_a_summary,
    )
    return _long_print_execution_summary(
        job_status=job_status,
        profile_id=profile_id,
        device_fingerprint=_required_json_string(
            _required_json_object(
                trusted_printer_summary,
                "device",
                "trusted-printer-record",
            ),
            "fingerprint",
            "trusted-printer-record.device",
        ),
    )


def record_long_print_reliability_artifact(
    *,
    stage_a_artifact_path: Path,
    protocol_sanity_artifact_path: Path,
    tiny_visual_card_artifact_path: Path,
    trusted_printer_record_path: Path,
    job_status: Mapping[str, object],
    output_dir: Path,
) -> Path:
    stage_a_summary = inspect_stage_a_artifact(stage_a_artifact_path)
    protocol_sanity_summary = _inspect_protocol_sanity_artifact(
        artifact_path=protocol_sanity_artifact_path,
        stage_a_summary=stage_a_summary,
    )
    tiny_visual_card_summary = _inspect_tiny_visual_card_artifact(
        artifact_path=tiny_visual_card_artifact_path,
        stage_a_summary=stage_a_summary,
        protocol_sanity_summary=protocol_sanity_summary,
    )
    trusted_printer_summary = _inspect_trusted_printer_record(
        record_path=trusted_printer_record_path,
        stage_a_artifact_path=stage_a_artifact_path,
        protocol_sanity_artifact_path=protocol_sanity_artifact_path,
        tiny_visual_card_artifact_path=tiny_visual_card_artifact_path,
        stage_a_summary=stage_a_summary,
    )
    _validate_confirmed_long_print_job(
        job_status=job_status,
        stage_a_summary=stage_a_summary,
    )

    job_id = _required_json_string(job_status, "jobId", "job-status")
    profile_id = _required_json_string(
        stage_a_summary,
        "profileId",
        "print-transfer-manifest.json",
    )
    device_fingerprint = _device_fingerprint(
        _required_json_string(stage_a_summary, "deviceId", "print-transfer-manifest.json")
    )
    trusted_sha = _required_json_string(
        trusted_printer_summary,
        "artifactSha256",
        "trusted-printer-record",
    )
    operator_confirmation = _required_json_object(
        job_status,
        "operatorConfirmation",
        "job-status",
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / (
        f"hardware-test-long-print-reliability-{_safe_filename_part(job_id)}.zip"
    )
    with ZipFile(artifact_path, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "stage-chain-summary.json",
            json.dumps(
                {
                    "stageA": {
                        "stage": "read_only_verification",
                        "status": _required_json_string(
                            stage_a_summary,
                            "status",
                            "print-transfer-manifest.json",
                        ),
                        "artifactSha256": hashlib.sha256(
                            stage_a_artifact_path.read_bytes()
                        ).hexdigest(),
                    },
                    "protocolSanity": {
                        "stage": "protocol_sanity_test",
                        "status": _required_json_string(
                            protocol_sanity_summary,
                            "status",
                            "protocol-sanity-summary",
                        ),
                        "artifactSha256": _required_json_string(
                            protocol_sanity_summary,
                            "artifactSha256",
                            "protocol-sanity-summary",
                        ),
                    },
                    "tinyVisualCard": {
                        "stage": "tiny_visual_test_card",
                        "status": _required_json_string(
                            tiny_visual_card_summary,
                            "status",
                            "tiny-visual-card-summary",
                        ),
                        "artifactSha256": _required_json_string(
                            tiny_visual_card_summary,
                            "artifactSha256",
                            "tiny-visual-card-summary",
                        ),
                    },
                    "trustedPrinter": {
                        "status": _required_json_string(
                            trusted_printer_summary,
                            "status",
                            "trusted-printer-record",
                        ),
                        "artifactSha256": trusted_sha,
                    },
                },
                indent=2,
            ),
        )
        archive.writestr(
            "trusted-printer-summary.json",
            json.dumps(
                {
                    "status": _required_json_string(
                        trusted_printer_summary,
                        "status",
                        "trusted-printer-record",
                    ),
                    "device": {
                        "idRedacted": True,
                        "fingerprint": device_fingerprint,
                    },
                    "profileId": profile_id,
                    "trustedFor": _required_json_string_list(
                        trusted_printer_summary,
                        "trustedFor",
                        "trusted-printer-record",
                    ),
                },
                indent=2,
            ),
        )
        archive.writestr(
            "long-print-job-summary.json",
            json.dumps(
                {
                    "jobId": job_id,
                    "profileId": profile_id,
                    "device": {
                        "idRedacted": True,
                        "fingerprint": device_fingerprint,
                    },
                    "state": _required_json_string(job_status, "state", "job-status"),
                    "completionLevel": _required_json_string(
                        job_status,
                        "completionLevel",
                        "job-status",
                    ),
                    "completionConfidence": _required_json_string(
                        job_status,
                        "completionConfidence",
                        "job-status",
                    ),
                    "requiresUserCheck": _required_json_bool(
                        job_status,
                        "requiresUserCheck",
                        "job-status",
                    ),
                    "rasterBytesIncluded": False,
                    "operatorNoteIncluded": False,
                },
                indent=2,
            ),
        )
        archive.writestr(
            "print-transfer-manifest.json",
            json.dumps(
                {
                    "stage": "long_print_reliability",
                    "status": "confirmed_complete",
                    "profileId": profile_id,
                    "jobId": job_id,
                    "requiredPriorStage": "trusted_printer_record",
                    "nextRequiredStage": "maintainer_review_for_stable_support",
                    "printCommandsSent": True,
                    "rasterBytesIncluded": False,
                    "operatorConfirmed": True,
                    "completionLevel": "verified",
                    "longPrintReliabilityPassed": True,
                    "priorStageArtifactSha256": trusted_sha,
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
                    "tailBlankRowsDots": _required_json_int(
                        job_status,
                        "tailBlankRowsDots",
                        "job-status",
                    ),
                    "rasterBytesIncluded": False,
                    "requiresLongPrintMode": True,
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
                    "stage": "long_print_reliability",
                    "longPrintReliabilityPassed": True,
                    "manualContinuousPrintingAlreadyTrusted": True,
                    "certificationComplete": False,
                    "stableSupportClaimEnabled": False,
                    "agentDirectPrintingEnabled": False,
                    "rasterBytesIncluded": False,
                },
                indent=2,
            ),
        )
        archive.writestr(
            "user-confirmation.json",
            json.dumps(
                {
                    "confirmedAt": _required_json_string(
                        operator_confirmation,
                        "confirmedAt",
                        "job-status.operatorConfirmation",
                    ),
                    "printedTextReadable": _required_json_bool(
                        operator_confirmation,
                        "printedTextReadable",
                        "job-status.operatorConfirmation",
                    ),
                    "endMarkerVisible": _required_json_bool(
                        operator_confirmation,
                        "endMarkerVisible",
                        "job-status.operatorConfirmation",
                    ),
                    "noOverheat": _required_json_bool(
                        operator_confirmation,
                        "noOverheat",
                        "job-status.operatorConfirmation",
                    ),
                    "noDisconnect": _required_json_bool(
                        operator_confirmation,
                        "noDisconnect",
                        "job-status.operatorConfirmation",
                    ),
                    "outcome": _required_json_string(
                        operator_confirmation,
                        "outcome",
                        "job-status.operatorConfirmation",
                    ),
                    "operatorNoteIncluded": False,
                },
                indent=2,
            ),
        )
        archive.writestr(
            "README.md",
            (
                "MiniX Print Studio Stage D long-print reliability hardware-test "
                "artifact. This archive records a reviewed long-print job summary, "
                "redacts device identity, excludes operator free text and raster bytes, "
                "and does not enable stable support or agent direct printing.\n"
            ),
        )
    return artifact_path


def record_stable_support_gate(
    *,
    stage_a_artifact_path: Path,
    protocol_sanity_artifact_path: Path,
    tiny_visual_card_artifact_path: Path,
    trusted_printer_record_path: Path,
    long_print_reliability_artifact_path: Path,
    output_dir: Path,
) -> Path:
    stage_a_summary = inspect_stage_a_artifact(stage_a_artifact_path)
    stage_a_artifact_sha = hashlib.sha256(stage_a_artifact_path.read_bytes()).hexdigest()
    protocol_sanity_summary = _inspect_protocol_sanity_artifact(
        artifact_path=protocol_sanity_artifact_path,
        stage_a_summary=stage_a_summary,
    )
    tiny_visual_card_summary = _inspect_tiny_visual_card_artifact(
        artifact_path=tiny_visual_card_artifact_path,
        stage_a_summary=stage_a_summary,
        protocol_sanity_summary=protocol_sanity_summary,
    )
    trusted_printer_summary = _inspect_trusted_printer_record(
        record_path=trusted_printer_record_path,
        stage_a_artifact_path=stage_a_artifact_path,
        protocol_sanity_artifact_path=protocol_sanity_artifact_path,
        tiny_visual_card_artifact_path=tiny_visual_card_artifact_path,
        stage_a_summary=stage_a_summary,
    )
    _inspect_long_print_reliability_artifact(
        artifact_path=long_print_reliability_artifact_path,
        stage_a_summary=stage_a_summary,
        stage_a_artifact_sha=stage_a_artifact_sha,
        protocol_sanity_summary=protocol_sanity_summary,
        tiny_visual_card_summary=tiny_visual_card_summary,
        trusted_printer_summary=trusted_printer_summary,
    )
    trusted_printer_artifact_sha = hashlib.sha256(
        trusted_printer_record_path.read_bytes()
    ).hexdigest()
    long_print_artifact_sha = hashlib.sha256(
        long_print_reliability_artifact_path.read_bytes()
    ).hexdigest()
    device_fingerprint = _device_fingerprint(
        _required_json_string(stage_a_summary, "deviceId", "print-transfer-manifest.json")
    )
    profile_id = _required_json_string(
        stage_a_summary,
        "profileId",
        "print-transfer-manifest.json",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    record_path = output_dir / (
        f"stable-support-gate-{device_fingerprint.removeprefix('sha256:')}.json"
    )
    record = {
        "schemaVersion": 1,
        "status": "stable_support_claims_enabled",
        "device": {
            "idRedacted": True,
            "fingerprint": device_fingerprint,
        },
        "profileId": profile_id,
        "trustedFor": [
            "manual_continuous_printing",
            "long_print_continuous_printing",
            "stable_support_claims",
        ],
        "operatorNoteIncluded": False,
        "rasterBytesIncluded": False,
        "hardwareEvidence": {
            "stageA": {
                "stage": "read_only_verification",
                "status": _required_json_string(
                    stage_a_summary,
                    "status",
                    "print-transfer-manifest.json",
                ),
                "artifactSha256": stage_a_artifact_sha,
            },
            "protocolSanity": {
                "stage": "protocol_sanity_test",
                "status": _required_json_string(
                    protocol_sanity_summary,
                    "status",
                    "protocol-sanity-summary",
                ),
                "artifactSha256": _required_json_string(
                    protocol_sanity_summary,
                    "artifactSha256",
                    "protocol-sanity-summary",
                ),
            },
            "tinyVisualCard": {
                "stage": "tiny_visual_test_card",
                "status": _required_json_string(
                    tiny_visual_card_summary,
                    "status",
                    "tiny-visual-card-summary",
                ),
                "artifactSha256": _required_json_string(
                    tiny_visual_card_summary,
                    "artifactSha256",
                    "tiny-visual-card-summary",
                ),
            },
            "trustedPrinter": {
                "stage": "trusted_printer_record",
                "status": "trusted_for_manual_continuous_printing",
                "artifactSha256": trusted_printer_artifact_sha,
            },
            "longPrintReliability": {
                "stage": "long_print_reliability",
                "status": "confirmed_complete",
                "artifactSha256": long_print_artifact_sha,
            },
        },
        "safety": {
            "manualContinuousPrintingEnabled": True,
            "longPrintReliabilityPassed": True,
            "longPrintPrintingEnabled": True,
            "stableSupportClaimEnabled": True,
            "agentDirectPrintingEnabled": False,
            "agentDirectPrintingDefault": "approval_required",
        },
        "nextRequiredStage": "agent_direct_printing_policy_review",
    }
    record_path.write_text(f"{json.dumps(record, indent=2)}\n", encoding="utf-8")
    return record_path


def _require_stage_a_artifact_files(archive: ZipFile) -> None:
    _require_artifact_files(
        archive,
        STAGE_A_ARTIFACT_REQUIRED_FILES,
        label="artifact",
    )


def _read_stage_a_profile(artifact_path: Path) -> dict[str, object]:
    try:
        with ZipFile(artifact_path) as archive:
            profile = _read_zip_json_object(archive, "profile.json")
    except FileNotFoundError as exc:
        raise HardwareTestCliError("artifact not found") from exc
    except BadZipFile as exc:
        raise HardwareTestCliError("artifact is not a ZIP file") from exc
    return profile


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


def _required_json_number(
    value: Mapping[str, object],
    field: str,
    filename: str,
) -> int | float:
    field_value = value.get(field)
    if not isinstance(field_value, int | float) or isinstance(field_value, bool):
        raise HardwareTestCliError(f"artifact missing required number: {filename}.{field}")
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


def _inspect_tiny_visual_card_artifact(
    *,
    artifact_path: Path,
    stage_a_summary: Mapping[str, object],
    protocol_sanity_summary: Mapping[str, object],
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
                    "protocol-sanity-summary.json",
                ),
                label="tiny visual card artifact",
            )
            transfer_manifest = _read_zip_json_object(
                archive,
                "print-transfer-manifest.json",
            )
            safety_report = _read_zip_json_object(archive, "safety-report.json")
            user_confirmation = _read_zip_json_object(archive, "user-confirmation.json")
            artifact_protocol_summary = _read_zip_json_object(
                archive,
                "protocol-sanity-summary.json",
            )
    except FileNotFoundError as exc:
        raise HardwareTestCliError("tiny visual card artifact not found") from exc
    except BadZipFile as exc:
        raise HardwareTestCliError("tiny visual card artifact is not a ZIP file") from exc

    _validate_tiny_visual_card_artifact(
        transfer_manifest=transfer_manifest,
        safety_report=safety_report,
        user_confirmation=user_confirmation,
        artifact_protocol_summary=artifact_protocol_summary,
        stage_a_summary=stage_a_summary,
        protocol_sanity_summary=protocol_sanity_summary,
    )
    return {
        "stage": "tiny_visual_test_card",
        "status": "confirmed_complete",
        "jobId": _required_json_string(
            transfer_manifest,
            "jobId",
            "print-transfer-manifest.json",
        ),
        "artifactSha256": artifact_sha256,
    }


def _validate_tiny_visual_card_artifact(
    *,
    transfer_manifest: Mapping[str, object],
    safety_report: Mapping[str, object],
    user_confirmation: Mapping[str, object],
    artifact_protocol_summary: Mapping[str, object],
    stage_a_summary: Mapping[str, object],
    protocol_sanity_summary: Mapping[str, object],
) -> None:
    if (
        _required_json_string(transfer_manifest, "stage", "print-transfer-manifest.json")
        != "tiny_visual_test_card"
    ):
        raise HardwareTestCliError("tiny visual card artifact has wrong stage")
    if (
        _required_json_string(transfer_manifest, "status", "print-transfer-manifest.json")
        != "confirmed_complete"
    ):
        raise HardwareTestCliError("tiny visual card artifact is not confirmed complete")
    if (
        _required_json_string(
            transfer_manifest,
            "nextRequiredStage",
            "print-transfer-manifest.json",
        )
        != "long_print_reliability"
    ):
        raise HardwareTestCliError("tiny visual card artifact is not ready for trusted record")
    if (
        _required_json_string(transfer_manifest, "deviceId", "print-transfer-manifest.json")
        != _required_json_string(stage_a_summary, "deviceId", "print-transfer-manifest.json")
    ):
        raise HardwareTestCliError("tiny visual card artifact device does not match Stage A")
    if (
        _required_json_string(transfer_manifest, "profileId", "print-transfer-manifest.json")
        != _required_json_string(stage_a_summary, "profileId", "print-transfer-manifest.json")
    ):
        raise HardwareTestCliError("tiny visual card artifact profile does not match Stage A")
    if (
        _required_json_string(
            transfer_manifest,
            "requiredPriorStage",
            "print-transfer-manifest.json",
        )
        != "protocol_sanity_test"
    ):
        raise HardwareTestCliError("tiny visual card artifact has wrong prior stage")
    if not _required_json_bool(
        transfer_manifest,
        "printCommandsSent",
        "print-transfer-manifest.json",
    ):
        raise HardwareTestCliError("tiny visual card artifact did not send print commands")
    if _required_json_bool(
        transfer_manifest,
        "rasterBytesIncluded",
        "print-transfer-manifest.json",
    ):
        raise HardwareTestCliError("tiny visual card artifact unexpectedly includes raster bytes")
    if not _required_json_bool(
        transfer_manifest,
        "operatorConfirmed",
        "print-transfer-manifest.json",
    ):
        raise HardwareTestCliError("tiny visual card artifact lacks operator confirmation")
    if (
        _required_json_string(
            transfer_manifest,
            "completionLevel",
            "print-transfer-manifest.json",
        )
        != "verified"
    ):
        raise HardwareTestCliError("tiny visual card artifact is not verified")

    prior_sha = _required_json_string(
        protocol_sanity_summary,
        "artifactSha256",
        "protocol-sanity-summary",
    )
    if (
        _required_json_string(
            transfer_manifest,
            "priorStageArtifactSha256",
            "print-transfer-manifest.json",
        )
        != prior_sha
        or _required_json_string(
            artifact_protocol_summary,
            "artifactSha256",
            "protocol-sanity-summary.json",
        )
        != prior_sha
    ):
        raise HardwareTestCliError("tiny visual card artifact is not chained to Stage B")

    if not _required_json_bool(safety_report, "printingLocked", "safety-report.json"):
        raise HardwareTestCliError("tiny visual card artifact safety unlocked printing")
    if _required_json_bool(safety_report, "certificationComplete", "safety-report.json"):
        raise HardwareTestCliError("tiny visual card artifact prematurely completed certification")
    if _required_json_bool(safety_report, "unlocksPrinting", "safety-report.json"):
        raise HardwareTestCliError("tiny visual card artifact unlocks printing")
    if not _required_json_bool(
        safety_report,
        "requiresLongPrintReliability",
        "safety-report.json",
    ):
        raise HardwareTestCliError("tiny visual card artifact skips long-print reliability")
    if _required_json_bool(safety_report, "rasterBytesIncluded", "safety-report.json"):
        raise HardwareTestCliError("tiny visual card safety report includes raster bytes")

    if (
        _required_json_string(user_confirmation, "outcome", "user-confirmation.json")
        != "confirmed_complete"
    ):
        raise HardwareTestCliError("tiny visual card operator confirmation is incomplete")
    for field in (
        "printedTextReadable",
        "endMarkerVisible",
        "noOverheat",
        "noDisconnect",
    ):
        if not _required_json_bool(user_confirmation, field, "user-confirmation.json"):
            raise HardwareTestCliError("tiny visual card operator checklist did not pass")


def _inspect_trusted_printer_record(
    *,
    record_path: Path,
    stage_a_artifact_path: Path,
    protocol_sanity_artifact_path: Path,
    tiny_visual_card_artifact_path: Path,
    stage_a_summary: Mapping[str, object],
) -> dict[str, object]:
    try:
        artifact_sha256 = hashlib.sha256(record_path.read_bytes()).hexdigest()
        decoded = json.loads(record_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HardwareTestCliError("trusted-printer record not found") from exc
    except json.JSONDecodeError as exc:
        raise HardwareTestCliError("trusted-printer record is invalid JSON") from exc
    if not isinstance(decoded, dict):
        raise HardwareTestCliError("trusted-printer record is not a JSON object")

    device_id = _required_json_string(
        stage_a_summary,
        "deviceId",
        "print-transfer-manifest.json",
    )
    profile_id = _required_json_string(
        stage_a_summary,
        "profileId",
        "print-transfer-manifest.json",
    )
    device = _required_json_object(decoded, "device", "trusted-printer-record")
    safety = _required_json_object(decoded, "safety", "trusted-printer-record")
    hardware_evidence = _required_json_object(
        decoded,
        "hardwareEvidence",
        "trusted-printer-record",
    )

    if _required_json_string(decoded, "status", "trusted-printer-record") != (
        "trusted_for_manual_continuous_printing"
    ):
        raise HardwareTestCliError("trusted-printer record has wrong status")
    if not _required_json_bool(device, "idRedacted", "trusted-printer-record.device"):
        raise HardwareTestCliError("trusted-printer record exposes raw device id")
    if _required_json_string(device, "fingerprint", "trusted-printer-record.device") != (
        _device_fingerprint(device_id)
    ):
        raise HardwareTestCliError("trusted-printer record device does not match Stage A")
    if _required_json_string(decoded, "profileId", "trusted-printer-record") != profile_id:
        raise HardwareTestCliError("trusted-printer record profile does not match Stage A")
    if "manual_continuous_printing" not in _required_json_string_list(
        decoded,
        "trustedFor",
        "trusted-printer-record",
    ):
        raise HardwareTestCliError("trusted-printer record does not trust manual printing")
    if not _required_json_bool(
        safety,
        "manualContinuousPrintingEnabled",
        "trusted-printer-record.safety",
    ):
        raise HardwareTestCliError("trusted-printer record does not enable manual printing")
    if not _required_json_bool(
        safety,
        "longPrintReliabilityRequired",
        "trusted-printer-record.safety",
    ):
        raise HardwareTestCliError("trusted-printer record skips long-print reliability")
    for field in (
        "longPrintPrintingEnabled",
        "agentDirectPrintingEnabled",
        "stableSupportClaimEnabled",
    ):
        if _required_json_bool(safety, field, "trusted-printer-record.safety"):
            raise HardwareTestCliError("trusted-printer record unlocks later-stage support")
    if _required_json_string(decoded, "nextRequiredStage", "trusted-printer-record") != (
        "long_print_reliability"
    ):
        raise HardwareTestCliError("trusted-printer record has wrong next stage")

    expected_artifacts = {
        "stageA": hashlib.sha256(stage_a_artifact_path.read_bytes()).hexdigest(),
        "protocolSanity": hashlib.sha256(protocol_sanity_artifact_path.read_bytes()).hexdigest(),
        "tinyVisualCard": hashlib.sha256(tiny_visual_card_artifact_path.read_bytes()).hexdigest(),
    }
    for field, expected_sha in expected_artifacts.items():
        evidence = _required_json_object(
            hardware_evidence,
            field,
            "trusted-printer-record.hardwareEvidence",
        )
        if (
            _required_json_string(
                evidence,
                "artifactSha256",
                f"trusted-printer-record.hardwareEvidence.{field}",
            )
            != expected_sha
        ):
            raise HardwareTestCliError("trusted-printer record evidence chain is stale")

    return {
        "status": _required_json_string(decoded, "status", "trusted-printer-record"),
        "device": {
            "idRedacted": True,
            "fingerprint": _device_fingerprint(device_id),
        },
        "profileId": profile_id,
        "trustedFor": _required_json_string_list(
            decoded,
            "trustedFor",
            "trusted-printer-record",
        ),
        "artifactSha256": artifact_sha256,
    }


def _inspect_long_print_reliability_artifact(
    *,
    artifact_path: Path,
    stage_a_summary: Mapping[str, object],
    stage_a_artifact_sha: str,
    protocol_sanity_summary: Mapping[str, object],
    tiny_visual_card_summary: Mapping[str, object],
    trusted_printer_summary: Mapping[str, object],
) -> dict[str, object]:
    try:
        artifact_sha256 = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        with ZipFile(artifact_path) as archive:
            _require_artifact_files(
                archive,
                (
                    "stage-chain-summary.json",
                    "trusted-printer-summary.json",
                    "long-print-job-summary.json",
                    "print-transfer-manifest.json",
                    "band-manifest.json",
                    "finalizer-result.json",
                    "safety-report.json",
                    "user-confirmation.json",
                ),
                label="long-print reliability artifact",
            )
            stage_chain = _read_zip_json_object(archive, "stage-chain-summary.json")
            trusted_summary = _read_zip_json_object(
                archive,
                "trusted-printer-summary.json",
            )
            job_summary = _read_zip_json_object(archive, "long-print-job-summary.json")
            transfer_manifest = _read_zip_json_object(
                archive,
                "print-transfer-manifest.json",
            )
            band_manifest = _read_zip_json_object(archive, "band-manifest.json")
            finalizer_result = _read_zip_json_object(archive, "finalizer-result.json")
            safety_report = _read_zip_json_object(archive, "safety-report.json")
            user_confirmation = _read_zip_json_object(archive, "user-confirmation.json")
    except FileNotFoundError as exc:
        raise HardwareTestCliError("long-print reliability artifact not found") from exc
    except BadZipFile as exc:
        raise HardwareTestCliError(
            "long-print reliability artifact is not a ZIP file"
        ) from exc

    _validate_long_print_reliability_artifact(
        stage_chain=stage_chain,
        trusted_summary=trusted_summary,
        job_summary=job_summary,
        transfer_manifest=transfer_manifest,
        band_manifest=band_manifest,
        finalizer_result=finalizer_result,
        safety_report=safety_report,
        user_confirmation=user_confirmation,
        stage_a_summary=stage_a_summary,
        stage_a_artifact_sha=stage_a_artifact_sha,
        protocol_sanity_summary=protocol_sanity_summary,
        tiny_visual_card_summary=tiny_visual_card_summary,
        trusted_printer_summary=trusted_printer_summary,
    )
    return {
        "stage": "long_print_reliability",
        "status": "confirmed_complete",
        "artifactSha256": artifact_sha256,
    }


def _validate_long_print_reliability_artifact(
    *,
    stage_chain: Mapping[str, object],
    trusted_summary: Mapping[str, object],
    job_summary: Mapping[str, object],
    transfer_manifest: Mapping[str, object],
    band_manifest: Mapping[str, object],
    finalizer_result: Mapping[str, object],
    safety_report: Mapping[str, object],
    user_confirmation: Mapping[str, object],
    stage_a_summary: Mapping[str, object],
    stage_a_artifact_sha: str,
    protocol_sanity_summary: Mapping[str, object],
    tiny_visual_card_summary: Mapping[str, object],
    trusted_printer_summary: Mapping[str, object],
) -> None:
    profile_id = _required_json_string(
        stage_a_summary,
        "profileId",
        "print-transfer-manifest.json",
    )
    device_fingerprint = _device_fingerprint(
        _required_json_string(stage_a_summary, "deviceId", "print-transfer-manifest.json")
    )
    trusted_sha = _required_json_string(
        trusted_printer_summary,
        "artifactSha256",
        "trusted-printer-record",
    )

    if (
        _required_json_string(transfer_manifest, "stage", "print-transfer-manifest.json")
        != "long_print_reliability"
    ):
        raise HardwareTestCliError("long-print reliability artifact has wrong stage")
    if (
        _required_json_string(transfer_manifest, "status", "print-transfer-manifest.json")
        != "confirmed_complete"
    ):
        raise HardwareTestCliError("long-print reliability artifact is not complete")
    if (
        _required_json_string(
            transfer_manifest,
            "requiredPriorStage",
            "print-transfer-manifest.json",
        )
        != "trusted_printer_record"
    ):
        raise HardwareTestCliError("long-print reliability artifact has wrong prior stage")
    if (
        _required_json_string(
            transfer_manifest,
            "nextRequiredStage",
            "print-transfer-manifest.json",
        )
        != "maintainer_review_for_stable_support"
    ):
        raise HardwareTestCliError("long-print reliability artifact skips stable review")
    if (
        _required_json_string(transfer_manifest, "profileId", "print-transfer-manifest.json")
        != profile_id
    ):
        raise HardwareTestCliError("long-print reliability artifact profile does not match")
    if (
        _required_json_string(
            transfer_manifest,
            "priorStageArtifactSha256",
            "print-transfer-manifest.json",
        )
        != trusted_sha
    ):
        raise HardwareTestCliError("long-print reliability artifact is not chained to trust")
    if not _required_json_bool(
        transfer_manifest,
        "printCommandsSent",
        "print-transfer-manifest.json",
    ):
        raise HardwareTestCliError("long-print reliability artifact did not send print commands")
    if _required_json_bool(
        transfer_manifest,
        "rasterBytesIncluded",
        "print-transfer-manifest.json",
    ):
        raise HardwareTestCliError("long-print reliability artifact includes raster bytes")
    if not _required_json_bool(
        transfer_manifest,
        "operatorConfirmed",
        "print-transfer-manifest.json",
    ):
        raise HardwareTestCliError("long-print reliability artifact lacks confirmation")
    if (
        _required_json_string(
            transfer_manifest,
            "completionLevel",
            "print-transfer-manifest.json",
        )
        != "verified"
    ):
        raise HardwareTestCliError("long-print reliability artifact is not verified")
    if not _required_json_bool(
        transfer_manifest,
        "longPrintReliabilityPassed",
        "print-transfer-manifest.json",
    ):
        raise HardwareTestCliError("long-print reliability artifact did not pass")

    if (
        _required_json_string(trusted_summary, "status", "trusted-printer-summary.json")
        != _required_json_string(
            trusted_printer_summary,
            "status",
            "trusted-printer-record",
        )
    ):
        raise HardwareTestCliError("long-print reliability trusted summary is stale")
    if (
        _required_json_string(trusted_summary, "profileId", "trusted-printer-summary.json")
        != profile_id
    ):
        raise HardwareTestCliError("long-print reliability trusted profile does not match")
    trusted_device = _required_json_object(
        trusted_summary,
        "device",
        "trusted-printer-summary.json",
    )
    if not _required_json_bool(
        trusted_device,
        "idRedacted",
        "trusted-printer-summary.json.device",
    ):
        raise HardwareTestCliError("long-print reliability trusted summary exposes device id")
    if (
        _required_json_string(
            trusted_device,
            "fingerprint",
            "trusted-printer-summary.json.device",
        )
        != device_fingerprint
    ):
        raise HardwareTestCliError("long-print reliability trusted device does not match")
    if "manual_continuous_printing" not in _required_json_string_list(
        trusted_summary,
        "trustedFor",
        "trusted-printer-summary.json",
    ):
        raise HardwareTestCliError("long-print reliability artifact lacks manual trust")

    job_device = _required_json_object(
        job_summary,
        "device",
        "long-print-job-summary.json",
    )
    if not _required_json_bool(job_device, "idRedacted", "long-print-job-summary.json.device"):
        raise HardwareTestCliError("long-print reliability job summary exposes device id")
    if (
        _required_json_string(
            job_device,
            "fingerprint",
            "long-print-job-summary.json.device",
        )
        != device_fingerprint
    ):
        raise HardwareTestCliError("long-print reliability job device does not match")
    if (
        _required_json_string(job_summary, "profileId", "long-print-job-summary.json")
        != profile_id
    ):
        raise HardwareTestCliError("long-print reliability job profile does not match")
    if (
        _required_json_string(job_summary, "state", "long-print-job-summary.json")
        != "confirmed_complete"
    ):
        raise HardwareTestCliError("long-print reliability job is not complete")
    if (
        _required_json_string(job_summary, "completionLevel", "long-print-job-summary.json")
        != "verified"
    ):
        raise HardwareTestCliError("long-print reliability job is not verified")
    if _required_json_bool(
        job_summary,
        "requiresUserCheck",
        "long-print-job-summary.json",
    ):
        raise HardwareTestCliError("long-print reliability job still requires a user check")
    if _required_json_bool(
        job_summary,
        "rasterBytesIncluded",
        "long-print-job-summary.json",
    ):
        raise HardwareTestCliError("long-print reliability job summary includes raster bytes")
    if _required_json_bool(
        job_summary,
        "operatorNoteIncluded",
        "long-print-job-summary.json",
    ):
        raise HardwareTestCliError("long-print reliability job summary includes operator note")

    for field, expected_total_field in (
        ("bandsSent", "totalBands"),
        ("rowsSent", "totalRows"),
        ("bytesSent", "totalBytes"),
    ):
        if _required_json_int(band_manifest, field, "band-manifest.json") != (
            _required_json_int(band_manifest, expected_total_field, "band-manifest.json")
        ):
            raise HardwareTestCliError("long-print reliability artifact is incomplete")
    if (
        _required_json_int(band_manifest, "totalBands", "band-manifest.json")
        < LONG_PRINT_RELIABILITY_MIN_BANDS
        or _required_json_int(band_manifest, "totalRows", "band-manifest.json")
        < LONG_PRINT_RELIABILITY_MIN_ROWS
    ):
        raise HardwareTestCliError("long-print reliability artifact is below coverage minimum")
    if not _required_json_bool(
        band_manifest,
        "requiresLongPrintMode",
        "band-manifest.json",
    ):
        raise HardwareTestCliError("long-print reliability artifact does not use long print mode")
    if _required_json_bool(band_manifest, "rasterBytesIncluded", "band-manifest.json"):
        raise HardwareTestCliError("long-print reliability band manifest includes raster bytes")

    if (
        _required_json_string(finalizer_result, "state", "finalizer-result.json")
        != "confirmed_complete"
    ):
        raise HardwareTestCliError("long-print reliability finalizer is not complete")
    if (
        _required_json_string(
            finalizer_result,
            "completionConfidence",
            "finalizer-result.json",
        )
        != "operator_paper_output_confirmed"
    ):
        raise HardwareTestCliError("long-print reliability finalizer lacks confirmation")

    if (
        _required_json_string(safety_report, "stage", "safety-report.json")
        != "long_print_reliability"
    ):
        raise HardwareTestCliError("long-print reliability safety has wrong stage")
    if not _required_json_bool(
        safety_report,
        "longPrintReliabilityPassed",
        "safety-report.json",
    ):
        raise HardwareTestCliError("long-print reliability safety did not pass")
    if not _required_json_bool(
        safety_report,
        "manualContinuousPrintingAlreadyTrusted",
        "safety-report.json",
    ):
        raise HardwareTestCliError("long-print reliability safety lost manual trust")
    if _required_json_bool(safety_report, "certificationComplete", "safety-report.json"):
        raise HardwareTestCliError("long-print reliability artifact already completed support")
    for field in ("stableSupportClaimEnabled", "agentDirectPrintingEnabled"):
        if _required_json_bool(safety_report, field, "safety-report.json"):
            raise HardwareTestCliError("long-print reliability artifact unlocks support early")
    if _required_json_bool(safety_report, "rasterBytesIncluded", "safety-report.json"):
        raise HardwareTestCliError("long-print reliability safety includes raster bytes")

    if (
        _required_json_string(user_confirmation, "outcome", "user-confirmation.json")
        != "confirmed_complete"
    ):
        raise HardwareTestCliError("long-print reliability confirmation is incomplete")
    for field in ("printedTextReadable", "endMarkerVisible", "noOverheat", "noDisconnect"):
        if not _required_json_bool(user_confirmation, field, "user-confirmation.json"):
            raise HardwareTestCliError("long-print reliability checklist did not pass")
    if _required_json_bool(
        user_confirmation,
        "operatorNoteIncluded",
        "user-confirmation.json",
    ):
        raise HardwareTestCliError("long-print reliability confirmation includes operator note")

    expected_chain = {
        "stageA": stage_a_artifact_sha,
        "protocolSanity": _required_json_string(
            protocol_sanity_summary,
            "artifactSha256",
            "protocol-sanity-summary",
        ),
        "tinyVisualCard": _required_json_string(
            tiny_visual_card_summary,
            "artifactSha256",
            "tiny-visual-card-summary",
        ),
        "trustedPrinter": trusted_sha,
    }
    for field, expected_sha in expected_chain.items():
        evidence = _required_json_object(
            stage_chain,
            field,
            "stage-chain-summary.json",
        )
        if (
            _required_json_string(
                evidence,
                "artifactSha256",
                f"stage-chain-summary.json.{field}",
            )
            != expected_sha
        ):
            raise HardwareTestCliError("long-print reliability evidence chain is stale")


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


def _validate_confirmed_long_print_job(
    *,
    job_status: Mapping[str, object],
    stage_a_summary: Mapping[str, object],
) -> None:
    if _required_json_string(job_status, "state", "job-status") != "confirmed_complete":
        raise HardwareTestCliError("long-print reliability job is not confirmed complete")
    if _required_json_string(job_status, "completionLevel", "job-status") != "verified":
        raise HardwareTestCliError("long-print reliability job is not verified")
    if (
        _required_json_string(job_status, "completionConfidence", "job-status")
        != "operator_paper_output_confirmed"
    ):
        raise HardwareTestCliError("long-print reliability job lacks operator confirmation")
    if _required_json_bool(job_status, "requiresUserCheck", "job-status"):
        raise HardwareTestCliError("long-print reliability job still requires user check")
    if (
        _required_json_string(job_status, "deviceId", "job-status")
        != _required_json_string(stage_a_summary, "deviceId", "print-transfer-manifest.json")
    ):
        raise HardwareTestCliError("long-print reliability job device does not match Stage A")

    bands_sent = _required_json_int(job_status, "bandsSent", "job-status")
    total_bands = _required_json_int(job_status, "totalBands", "job-status")
    rows_sent = _required_json_int(job_status, "rowsSent", "job-status")
    total_rows = _required_json_int(job_status, "totalRows", "job-status")
    bytes_sent = _required_json_int(job_status, "bytesSent", "job-status")
    total_bytes = _required_json_int(job_status, "totalBytes", "job-status")
    tail_rows = _required_json_int(job_status, "tailBlankRowsDots", "job-status")
    if bands_sent != total_bands or rows_sent != total_rows or bytes_sent != total_bytes:
        raise HardwareTestCliError("long-print reliability job did not send all planned data")
    if total_bands < LONG_PRINT_RELIABILITY_MIN_BANDS:
        raise HardwareTestCliError("long-print reliability job is not banded enough")
    if total_rows < LONG_PRINT_RELIABILITY_MIN_ROWS:
        raise HardwareTestCliError("long-print reliability job is too short")
    if tail_rows < LONG_PRINT_RELIABILITY_MIN_TAIL_ROWS:
        raise HardwareTestCliError("long-print reliability job lacks protected tail rows")

    confirmation = _required_json_object(job_status, "operatorConfirmation", "job-status")
    if _required_json_string(confirmation, "outcome", "job-status.operatorConfirmation") != (
        "confirmed_complete"
    ):
        raise HardwareTestCliError("long-print reliability operator confirmation is incomplete")
    for field in (
        "printedTextReadable",
        "endMarkerVisible",
        "noOverheat",
        "noDisconnect",
    ):
        if not _required_json_bool(confirmation, field, "job-status.operatorConfirmation"):
            raise HardwareTestCliError("long-print reliability operator checklist did not pass")


def _validate_started_long_print_job(
    *,
    job_status: Mapping[str, object],
    stage_a_summary: Mapping[str, object],
) -> None:
    state = _required_json_string(job_status, "state", "job-status")
    if state != "completed_unverified":
        raise HardwareTestCliError("long-print reliability print did not complete transfer")
    if _required_json_string(job_status, "completionLevel", "job-status") != "unverified":
        raise HardwareTestCliError("long-print reliability print has unexpected completion level")
    if not _required_json_bool(job_status, "requiresUserCheck", "job-status"):
        raise HardwareTestCliError("long-print reliability print skipped operator check")
    if (
        _required_json_string(job_status, "source", "job-status")
        != LONG_PRINT_RELIABILITY_SOURCE
    ):
        raise HardwareTestCliError("long-print reliability print source is invalid")
    if (
        _required_json_string(job_status, "deviceId", "job-status")
        != _required_json_string(stage_a_summary, "deviceId", "print-transfer-manifest.json")
    ):
        raise HardwareTestCliError("long-print reliability print device does not match Stage A")
    if "confirm_complete" not in _required_json_string_list(
        job_status,
        "safeActions",
        "job-status",
    ):
        raise HardwareTestCliError("long-print reliability print cannot be operator-confirmed")

    bands_sent = _required_json_int(job_status, "bandsSent", "job-status")
    total_bands = _required_json_int(job_status, "totalBands", "job-status")
    rows_sent = _required_json_int(job_status, "rowsSent", "job-status")
    total_rows = _required_json_int(job_status, "totalRows", "job-status")
    bytes_sent = _required_json_int(job_status, "bytesSent", "job-status")
    total_bytes = _required_json_int(job_status, "totalBytes", "job-status")
    tail_rows = _required_json_int(job_status, "tailBlankRowsDots", "job-status")
    if bands_sent != total_bands or rows_sent != total_rows or bytes_sent != total_bytes:
        raise HardwareTestCliError("long-print reliability print did not send all planned data")
    if total_bands < LONG_PRINT_RELIABILITY_MIN_BANDS:
        raise HardwareTestCliError("long-print reliability print is not banded enough")
    if total_rows < LONG_PRINT_RELIABILITY_MIN_ROWS:
        raise HardwareTestCliError("long-print reliability print is too short")
    if tail_rows < LONG_PRINT_RELIABILITY_MIN_TAIL_ROWS:
        raise HardwareTestCliError("long-print reliability print lacks protected tail rows")


def _long_print_execution_summary(
    *,
    job_status: Mapping[str, object],
    profile_id: str,
    device_fingerprint: str,
) -> dict[str, object]:
    return {
        "status": "long_print_reliability_print_started",
        "jobId": _required_json_string(job_status, "jobId", "job-status"),
        "profileId": profile_id,
        "device": {
            "idRedacted": True,
            "fingerprint": device_fingerprint,
        },
        "state": _required_json_string(job_status, "state", "job-status"),
        "completionLevel": _required_json_string(
            job_status,
            "completionLevel",
            "job-status",
        ),
        "completionConfidence": _required_json_string(
            job_status,
            "completionConfidence",
            "job-status",
        ),
        "requiresUserCheck": _required_json_bool(
            job_status,
            "requiresUserCheck",
            "job-status",
        ),
        "bandsSent": _required_json_int(job_status, "bandsSent", "job-status"),
        "totalBands": _required_json_int(job_status, "totalBands", "job-status"),
        "rowsSent": _required_json_int(job_status, "rowsSent", "job-status"),
        "totalRows": _required_json_int(job_status, "totalRows", "job-status"),
        "bytesSent": _required_json_int(job_status, "bytesSent", "job-status"),
        "totalBytes": _required_json_int(job_status, "totalBytes", "job-status"),
        "tailBlankRowsDots": _required_json_int(
            job_status,
            "tailBlankRowsDots",
            "job-status",
        ),
        "confirmationRequired": True,
        "nextRequiredStage": "operator_confirmation_then_record_long_print_reliability",
        "stableSupportClaimEnabled": False,
        "agentDirectPrintingEnabled": False,
        "rasterBytesIncluded": False,
    }


def _device_fingerprint(device_id: str) -> str:
    return f"sha256:{hashlib.sha256(device_id.encode('utf-8')).hexdigest()[:16]}"


def _stable_json_sha256(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


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


def _build_long_print_reliability_raster(width_dots: int, height_dots: int) -> bytes:
    row_bytes = width_dots // 8
    raster = bytearray(row_bytes * height_dots)
    for text, y in LONG_PRINT_RELIABILITY_MARKERS:
        _draw_text(
            raster,
            width_dots=width_dots,
            text=text,
            x=24,
            y=y,
            scale=2,
        )
        for rule_y in range(y + 22, min(y + 24, height_dots)):
            for x in range(24, width_dots - 24, 3):
                _set_raster_pixel(raster, width_dots, x, rule_y)
        for tick_y in range(y, min(y + 36, height_dots), 4):
            for x in range(0, 5):
                _set_raster_pixel(raster, width_dots, x, tick_y)
            for x in range(width_dots - 5, width_dots):
                _set_raster_pixel(raster, width_dots, x, tick_y)

    for y in range(0, height_dots, 400):
        for x in range(12, width_dots - 12, 32):
            _set_raster_pixel(raster, width_dots, x, y)
            _set_raster_pixel(raster, width_dots, x, min(y + 1, height_dots - 1))

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
