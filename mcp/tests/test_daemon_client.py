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
