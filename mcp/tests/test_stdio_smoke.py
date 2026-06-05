import contextlib
import http.server
import json
import os
import sys
import threading
from pathlib import Path
from typing import Any

import pytest
from mcp import ClientSession, StdioServerParameters, stdio_client

from minix_mcp.stdio_smoke import run_mcp_stdio_smoke


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_mcp_stdio_smoke_reaches_daemon_through_runtime_handoff(tmp_path: Path) -> None:
    token = "token_stdio_smoke"
    with mock_daemon(token) as base_url:
        runtime_file = write_runtime_handoff(tmp_path, base_url, token)

        result = await run_mcp_stdio_smoke(
            command=sys.executable,
            args=["-m", "minix_mcp"],
            env=stdio_env(runtime_file),
        )

    assert result == {
        "status": "ok",
        "daemon": {
            "ok": True,
            "version": "0.1.0",
            "profileRegistryVersion": "2026.06.04",
            "mock": True,
        },
    }


@pytest.mark.anyio
async def test_mcp_stdio_process_smoke_uses_real_server(tmp_path: Path) -> None:
    token = "token_stdio_real"
    with mock_daemon(token) as base_url:
        runtime_file = write_runtime_handoff(tmp_path, base_url, token)
        server = StdioServerParameters(
            command=sys.executable,
            args=["-m", "minix_mcp"],
            env=stdio_env(runtime_file),
        )

        async with stdio_client(server) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                response = await session.call_tool("get_daemon_status", {})

    assert response.structuredContent is not None
    assert response.structuredContent["status"] == "ok"
    assert response.structuredContent["daemon"]["mock"] is True


@pytest.mark.anyio
async def test_mcp_stdio_packaged_binary_smoke(tmp_path: Path) -> None:
    binary = os.environ.get("MINIX_MCP_BINARY_SMOKE")
    if not binary:
        pytest.skip("set MINIX_MCP_BINARY_SMOKE to a built minix-mcp binary")

    token = "token_stdio_binary"
    binary_path = Path(binary).resolve()
    assert binary_path.is_file()

    with mock_daemon(token) as base_url:
        runtime_file = write_runtime_handoff(tmp_path, base_url, token)
        result = await run_mcp_stdio_smoke(
            command=str(binary_path),
            env=stdio_env(runtime_file, include_pythonpath=False),
        )

    assert result == {
        "status": "ok",
        "daemon": {
            "ok": True,
            "version": "0.1.0",
            "profileRegistryVersion": "2026.06.04",
            "mock": True,
        },
    }


def write_runtime_handoff(tmp_path: Path, base_url: str, token: str) -> Path:
    token_file = tmp_path / "token"
    runtime_file = tmp_path / "runtime.json"
    token_file.write_text(token, encoding="utf-8")
    runtime_file.write_text(
        json.dumps(
            {
                "version": 1,
                "pid": 123,
                "baseUrl": base_url,
                "tokenFile": str(token_file),
                "startedAt": "2026-06-05T00:00:00.000Z",
                "mock": True,
            }
        ),
        encoding="utf-8",
    )
    return runtime_file


@contextlib.contextmanager
def mock_daemon(token: str):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), MockDaemonHandler)
    server.expected_token = token  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class MockDaemonHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/v1/health":
            self.send_error(404)
            return
        expected_token = self.server.expected_token  # type: ignore[attr-defined]
        if self.headers.get("Authorization") != f"Bearer {expected_token}":
            self.send_error(401)
            return
        self.send_json(
            {
                "ok": True,
                "version": "0.1.0",
                "profileRegistryVersion": "2026.06.04",
                "mock": True,
            }
        )

    def send_json(self, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: Any) -> None:
        return


def stdio_env(runtime_file: Path, *, include_pythonpath: bool = True) -> dict[str, str]:
    env = {
        "MINIX_DAEMON_RUNTIME_FILE": str(runtime_file),
    }
    if include_pythonpath:
        env["PYTHONPATH"] = str(Path(__file__).parents[1] / "src")
    return env
