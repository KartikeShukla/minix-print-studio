import json
from collections.abc import Mapping

from minix_mcp.daemon_client import DaemonHttpClient, JsonObject


def test_daemon_http_client_posts_document_preview_with_auth_headers() -> None:
    calls: list[tuple[str, str, bytes | None, Mapping[str, str], float]] = []

    def transport(
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout: float,
    ) -> JsonObject:
        calls.append((method, url, body, headers, timeout))
        return {
            "previewId": "prev_mcp",
            "approvalToken": "appr_secret",
            "documentHash": "sha256:document",
            "renderSettingsHash": "sha256:settings",
            "profileId": "seznik-minix-s1-lyin48d-gy",
            "widthDots": 384,
            "heightDots": 200,
            "expiresAt": "2026-06-04T00:10:00.000Z",
        }

    client = DaemonHttpClient(
        base_url="http://127.0.0.1:39281",
        token="secret-token",
        transport=transport,
        timeout=2.5,
    )

    response = client.create_document_preview(
        document={"schemaVersion": 1},
        render_settings={"threshold": 128, "dither": "none"},
    )

    assert response["previewId"] == "prev_mcp"
    assert len(calls) == 1
    method, url, body, headers, timeout = calls[0]
    assert method == "POST"
    assert url == "http://127.0.0.1:39281/v1/render/document-preview"
    assert headers == {
        "Authorization": "Bearer secret-token",
        "Content-Type": "application/json",
    }
    assert timeout == 2.5
    assert body is not None
    assert json.loads(body.decode("utf-8")) == {
        "document": {"schemaVersion": 1},
        "renderSettings": {"threshold": 128, "dither": "none"},
    }


def test_daemon_http_client_gets_health_with_auth_headers() -> None:
    calls: list[tuple[str, str, bytes | None, Mapping[str, str], float]] = []

    def transport(
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout: float,
    ) -> JsonObject:
        calls.append((method, url, body, headers, timeout))
        return {
            "ok": True,
            "version": "0.1.0",
            "profileRegistryVersion": "2026.06.04",
            "mock": True,
        }

    client = DaemonHttpClient(
        base_url="http://127.0.0.1:39281/",
        token="secret-token",
        transport=transport,
    )

    assert client.get_health()["ok"] is True
    assert calls == [
        (
            "GET",
            "http://127.0.0.1:39281/v1/health",
            None,
            {"Authorization": "Bearer secret-token"},
            5.0,
        )
    ]


def test_daemon_http_client_gets_job_status_with_auth_headers() -> None:
    calls: list[tuple[str, str, bytes | None, Mapping[str, str], float]] = []

    def transport(
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout: float,
    ) -> JsonObject:
        calls.append((method, url, body, headers, timeout))
        return {
            "jobId": "job_123",
            "state": "completed_unverified",
            "completionLevel": "unverified",
            "requiresUserCheck": True,
            "safeActions": ["confirm_complete"],
        }

    client = DaemonHttpClient(
        base_url="http://127.0.0.1:39281/",
        token="secret-token",
        transport=transport,
        timeout=3.0,
    )

    assert client.get_job_status("job_123/unsafe id")["completionLevel"] == "unverified"
    assert calls == [
        (
            "GET",
            "http://127.0.0.1:39281/v1/jobs/job_123%2Funsafe%20id",
            None,
            {"Authorization": "Bearer secret-token"},
            3.0,
        )
    ]
