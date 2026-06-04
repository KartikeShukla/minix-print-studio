import json

import pytest

from minix_mcp.runtime import resolve_daemon_runtime


def test_resolves_daemon_runtime_from_electron_handoff_file(tmp_path) -> None:
    token_file = tmp_path / "token"
    runtime_file = tmp_path / "runtime.json"
    token_file.write_text("token_private\n", encoding="utf-8")
    runtime_file.write_text(
        json.dumps(
            {
                "version": 1,
                "pid": 12345,
                "baseUrl": "http://127.0.0.1:43210",
                "tokenFile": str(token_file),
                "startedAt": "2026-06-04T10:00:00.000Z",
            }
        ),
        encoding="utf-8",
    )

    runtime = resolve_daemon_runtime({"MINIX_DAEMON_RUNTIME_FILE": str(runtime_file)})

    assert runtime.base_url == "http://127.0.0.1:43210"
    assert runtime.token == "token_private"


def test_resolve_daemon_runtime_rejects_runtime_file_with_inline_token(tmp_path) -> None:
    runtime_file = tmp_path / "runtime.json"
    runtime_file.write_text(
        json.dumps(
            {
                "version": 1,
                "baseUrl": "http://127.0.0.1:43210",
                "token": "inline-secret",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="tokenFile"):
        resolve_daemon_runtime({"MINIX_DAEMON_RUNTIME_FILE": str(runtime_file)})
