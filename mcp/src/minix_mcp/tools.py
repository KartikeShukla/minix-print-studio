from __future__ import annotations

from typing import Protocol, cast

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
JOB_STATUS_REDACTED_KEYS = frozenset(
    {
        "approvalToken",
        "approval_token",
        "raster",
        "rasterBase64",
        "rawRaster",
        "segments",
    }
)


class DaemonClient(Protocol):
    def get_health(self) -> JsonObject: ...

    def create_document_preview(
        self,
        *,
        document: JsonObject,
        render_settings: JsonObject,
    ) -> JsonObject: ...

    def get_job_status(self, job_id: str) -> JsonObject: ...

    def get_profiles(self) -> JsonObject: ...


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


def get_job_status_tool(client: DaemonClient, *, job_id: str) -> JsonObject:
    try:
        job = client.get_job_status(job_id)
    except DaemonUnavailable:
        return build_app_not_running_response()

    return {"status": "ok", "job": _redacted_job_status(job)}


def list_supported_profiles_tool(client: DaemonClient) -> JsonObject:
    try:
        response = client.get_profiles()
    except DaemonUnavailable:
        return build_app_not_running_response()

    profiles = response.get("profiles")
    if not isinstance(profiles, list):
        raise ValueError("profiles must be a list")
    return {
        "status": "ok",
        "profiles": [
            _profile_summary(cast(JsonObject, profile))
            for profile in profiles
            if isinstance(profile, dict)
        ],
    }


def _redacted_job_status(job: JsonObject) -> JsonObject:
    return {
        key: value
        for key, value in job.items()
        if key not in JOB_STATUS_REDACTED_KEYS
    }


def _profile_summary(profile: JsonObject) -> JsonObject:
    summary: JsonObject = {"id": _string_value(profile, "id")}
    _copy_optional_string(summary, profile, "displayName")
    _copy_optional_string(summary, profile, "supportLevel")
    _copy_optional_string(summary, profile, "profileVersion")
    _copy_optional_string(summary, profile, "manufacturer")
    _copy_optional_string(summary, profile, "modelResponse")

    observed_firmware = _optional_string_list_value(profile, "observedFirmware")
    if observed_firmware is not None:
        summary["observedFirmware"] = observed_firmware

    print_config = _optional_object_value(profile, "print")
    if print_config is not None:
        summary["print"] = _print_profile_summary(print_config)

    safety = _optional_object_value(profile, "safety")
    if safety is not None:
        safety_limits: JsonObject = {}
        _copy_optional_int(safety_limits, safety, "maxHeightDotsAgentDirect")
        _copy_optional_int(safety_limits, safety, "maxCopiesAgentDirect")
        if safety_limits:
            summary["agentSafetyLimits"] = safety_limits

    return summary


def _print_profile_summary(print_config: JsonObject) -> JsonObject:
    summary: JsonObject = {}
    _copy_optional_int(summary, print_config, "widthDots")
    _copy_optional_int(summary, print_config, "rowBytes")
    _copy_optional_string(summary, print_config, "defaultPaperMode")
    _copy_optional_string(summary, print_config, "defaultDensity")
    paper_modes = _optional_string_list_value(print_config, "paperModes")
    if paper_modes is not None:
        summary["paperModes"] = paper_modes
    density_modes = _optional_string_list_value(print_config, "densityModes")
    if density_modes is not None:
        summary["densityModes"] = density_modes
    return summary


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


def _copy_optional_string(target: JsonObject, source: JsonObject, key: str) -> None:
    value = source.get(key)
    if isinstance(value, str):
        target[key] = value


def _copy_optional_int(target: JsonObject, source: JsonObject, key: str) -> None:
    value = source.get(key)
    if isinstance(value, int):
        target[key] = value


def _optional_string_list_value(source: JsonObject, key: str) -> list[JsonValue] | None:
    value = source.get(key)
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{key} must be a string list")
    return cast(list[JsonValue], value)


def _optional_object_value(source: JsonObject, key: str) -> JsonObject | None:
    value = source.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value
