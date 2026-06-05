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


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


type HttpTransport = Callable[[str, str, bytes | None, Mapping[str, str], float], HttpResponse]


class HardwareTestCliError(RuntimeError):
    """Raised when the hardware-test CLI cannot complete the requested operation."""


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
    return parser


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
