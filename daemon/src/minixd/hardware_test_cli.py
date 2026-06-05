from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO, cast
from zipfile import BadZipFile, ZipFile

from minixd.protocol.aiyin import (
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


class HardwareTestCliError(RuntimeError):
    """Raised when the hardware-test CLI cannot complete the requested operation."""


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


def _protocol_command(index: int, name: str, payload: bytes) -> dict[str, object]:
    return {
        "index": index,
        "name": name,
        "payloadBytes": len(payload),
        "hex": _hex(payload),
    }


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
