from __future__ import annotations

from typing import Protocol

from minix_mcp.daemon_client import (
    DaemonUnavailable,
    JsonObject,
    JsonValue,
    build_app_not_running_response,
)

DEFAULT_RENDER_SETTINGS: JsonObject = {"threshold": 128, "dither": "none"}
DEFAULT_AGENT_POLICY: JsonObject = {
    "directPrint": False,
    "requireTrustedPrinter": True,
    "rateLimitJobsPerMinute": 3,
}


class DaemonClient(Protocol):
    def get_health(self) -> JsonObject: ...

    def create_document_preview(
        self,
        *,
        document: JsonObject,
        render_settings: JsonObject,
    ) -> JsonObject: ...


def get_daemon_status_tool(client: DaemonClient) -> JsonObject:
    try:
        return {"status": "ok", "daemon": client.get_health()}
    except DaemonUnavailable:
        return build_app_not_running_response()


def preview_document_tool(
    client: DaemonClient,
    *,
    document: JsonObject,
    render_settings: JsonObject,
) -> JsonObject:
    try:
        preview = client.create_document_preview(
            document=document,
            render_settings=render_settings,
        )
    except DaemonUnavailable:
        return build_app_not_running_response()

    return _approval_required_response(preview)


def print_note_tool(
    client: DaemonClient,
    *,
    text: str,
    title: str = "Agent note",
) -> JsonObject:
    try:
        preview = client.create_document_preview(
            document=_build_note_document(text=text, title=title),
            render_settings=DEFAULT_RENDER_SETTINGS,
        )
    except DaemonUnavailable:
        return build_app_not_running_response()

    return _approval_required_response(
        preview,
        policy_decision=_agent_policy_decision(tool_name="print_note"),
    )


def _approval_required_response(
    preview: JsonObject,
    *,
    policy_decision: JsonObject | None = None,
) -> JsonObject:
    preview_id = _string_value(preview, "previewId")
    response: JsonObject = {
        "status": "approval_required",
        "previewId": preview_id,
        "approvalUrl": f"minixprint://approval/{preview_id}",
        "documentHash": _string_value(preview, "documentHash"),
        "renderSettingsHash": _string_value(preview, "renderSettingsHash"),
        "profileId": _string_value(preview, "profileId"),
        "widthDots": _int_value(preview, "widthDots"),
        "heightDots": _int_value(preview, "heightDots"),
        "expiresAt": _string_value(preview, "expiresAt"),
        "message": "Preview created. User approval is required before printing.",
    }
    safety = _optional_object_value(preview, "safety")
    if safety is not None:
        response["safety"] = safety
    if policy_decision is not None:
        response["policyDecision"] = policy_decision
    return response


def _agent_policy_decision(*, tool_name: str) -> JsonObject:
    return {
        "tool": tool_name,
        "directPrintAllowed": False,
        "reasons": ["agent_direct_print_disabled", "printer_not_trusted"],
        "rateLimit": {
            "jobsPerMinute": _int_value(DEFAULT_AGENT_POLICY, "rateLimitJobsPerMinute")
        },
    }


def _build_note_document(*, text: str, title: str) -> JsonObject:
    height_dots = _note_height(text)
    return {
        "schemaVersion": 1,
        "id": "mcp_note",
        "title": title,
        "target": {
            "profileId": "seznik-minix-s1-lyin48d-gy",
            "widthDots": 384,
            "heightDots": height_dots,
            "dpi": 203,
            "paperMode": "continuous",
            "density": "medium",
        },
        "background": {"color": "#ffffff"},
        "elements": [
            {
                "id": "text_note",
                "type": "text",
                "name": "Note text",
                "x": 12,
                "y": 12,
                "width": 360,
                "height": height_dots - 24,
                "rotation": 0,
                "locked": False,
                "visible": True,
                "text": text,
                "style": {"fill": "#000000", "fontFamily": "default", "fontSize": 12},
            }
        ],
        "assets": [],
        "metadata": {"source": "mcp"},
    }


def _note_height(text: str) -> int:
    line_count = max(1, len(text.splitlines()))
    return max(160, min(1000, 40 + (line_count * 18)))


def _string_value(source: JsonObject, key: str) -> str:
    value = source.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _int_value(source: JsonObject, key: str) -> int:
    value: JsonValue = source.get(key)
    if not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return value


def _optional_object_value(source: JsonObject, key: str) -> JsonObject | None:
    value = source.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value
