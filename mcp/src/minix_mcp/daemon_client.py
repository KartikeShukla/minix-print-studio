from __future__ import annotations


def build_app_not_running_response() -> dict[str, bool | str]:
    return {
        "status": "app_not_running",
        "message": (
            "MiniX Print Studio is not running. Open the desktop app or enable "
            "background agent service."
        ),
        "requiresUserAction": True,
    }
