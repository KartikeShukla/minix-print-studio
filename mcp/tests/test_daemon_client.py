import pytest

from minix_mcp.__main__ import main
from minix_mcp.daemon_client import build_app_not_running_response


def test_app_not_running_response_is_structured() -> None:
    response = build_app_not_running_response()

    assert response == {
        "status": "app_not_running",
        "message": (
            "MiniX Print Studio is not running. Open the desktop app or enable "
            "background agent service."
        ),
        "requiresUserAction": True,
    }


def test_main_runs_stdio_server(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[bool] = []

    def fake_run_stdio_server() -> None:
        calls.append(True)

    monkeypatch.setattr("minix_mcp.__main__.run_stdio_server", fake_run_stdio_server)

    main()

    assert calls == [True]
