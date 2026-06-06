from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from typing import cast
from urllib.parse import quote

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]
type HttpTransport = Callable[[str, str, bytes | None, Mapping[str, str], float], JsonObject]


class DaemonUnavailable(RuntimeError):
    """Raised when the desktop daemon is not reachable."""


class DaemonRequestError(RuntimeError):
    """Raised when the daemon returns an error or malformed response."""


def build_app_not_running_response() -> JsonObject:
    return {
        "status": "app_not_running",
        "message": (
            "MiniX Print Studio is not running. Open the desktop app or enable "
            "background agent service."
        ),
        "requiresUserAction": True,
    }


class DaemonHttpClient:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        transport: HttpTransport | None = None,
        timeout: float = 5.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._transport = transport or urllib_transport
        self._timeout = timeout

    def get_health(self) -> JsonObject:
        return self._request("GET", "/v1/health")

    def create_document_preview(
        self,
        *,
        document: JsonObject,
        render_settings: JsonObject,
    ) -> JsonObject:
        return self._request(
            "POST",
            "/v1/render/document-preview",
            body={"document": document, "renderSettings": render_settings},
        )

    def get_job_status(self, job_id: str) -> JsonObject:
        return self._request("GET", f"/v1/jobs/{quote(job_id, safe='')}")

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: JsonObject | None = None,
    ) -> JsonObject:
        headers: dict[str, str] = {"Authorization": f"Bearer {self._token}"}
        encoded_body: bytes | None = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            encoded_body = json.dumps(body).encode("utf-8")

        return self._transport(
            method,
            f"{self._base_url}{path}",
            encoded_body,
            headers,
            self._timeout,
        )


def urllib_transport(
    method: str,
    url: str,
    body: bytes | None,
    headers: Mapping[str, str],
    timeout: float,
) -> JsonObject:
    request = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return _decode_json_response(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise DaemonRequestError(f"daemon returned HTTP {exc.code}: {detail}") from exc
    except (TimeoutError, urllib.error.URLError) as exc:
        raise DaemonUnavailable("daemon unavailable") from exc


def _decode_json_response(payload: bytes) -> JsonObject:
    decoded = json.loads(payload.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise DaemonRequestError("daemon returned non-object JSON")
    return cast(JsonObject, decoded)
