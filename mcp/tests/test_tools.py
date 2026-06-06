from minix_mcp.daemon_client import DaemonUnavailable, JsonObject
from minix_mcp.tools import (
    get_daemon_status_tool,
    get_job_status_tool,
    preview_document_tool,
    print_note_tool,
)


class StubDaemonClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.preview_calls: list[tuple[JsonObject, JsonObject]] = []

    def get_health(self) -> JsonObject:
        if self.fail:
            raise DaemonUnavailable("daemon unavailable")
        return {
            "ok": True,
            "version": "0.1.0",
            "profileRegistryVersion": "2026.06.04",
            "mock": True,
        }

    def create_document_preview(
        self,
        *,
        document: JsonObject,
        render_settings: JsonObject,
    ) -> JsonObject:
        if self.fail:
            raise DaemonUnavailable("daemon unavailable")
        self.preview_calls.append((document, render_settings))
        return {
            "previewId": "prev_agent",
            "approvalToken": "appr_do_not_expose",
            "documentHash": "sha256:document",
            "renderSettingsHash": "sha256:settings",
            "profileId": "seznik-minix-s1-lyin48d-gy",
            "widthDots": 384,
            "heightDots": 240,
            "safety": {
                "allowed": True,
                "warnings": [],
                "metrics": {"totalBlackCoverage": 0.08, "maxBandCoverage64": 0.12},
            },
            "expiresAt": "2026-06-04T00:10:00.000Z",
        }

    def get_job_status(self, job_id: str) -> JsonObject:
        if self.fail:
            raise DaemonUnavailable("daemon unavailable")
        return {
            "jobId": job_id,
            "state": "completed_unverified",
            "phase": "waiting_for_final_status",
            "completionLevel": "unverified",
            "completionConfidence": "mock_data_sent_final_ack_missing",
            "requiresUserCheck": True,
            "bandsSent": 2,
            "totalBands": 2,
            "safeActions": ["confirm_complete", "feed_paper", "reprint_from_start"],
            "approvalToken": "secret-approval-token",
            "raster": "raw-raster-bytes",
            "segments": [{"payload": "raw-segment"}],
        }


def test_daemon_status_tool_returns_health() -> None:
    response = get_daemon_status_tool(StubDaemonClient())

    assert response == {
        "status": "ok",
        "daemon": {
            "ok": True,
            "version": "0.1.0",
            "profileRegistryVersion": "2026.06.04",
            "mock": True,
        },
    }


def test_preview_document_returns_approval_required_without_leaking_token() -> None:
    client = StubDaemonClient()
    response = preview_document_tool(
        client,
        document={"schemaVersion": 1, "target": {"profileId": "seznik-minix-s1-lyin48d-gy"}},
        render_settings={"threshold": 128},
    )

    assert response == {
        "status": "approval_required",
        "previewId": "prev_agent",
        "approvalUrl": "minixprint://approval/prev_agent",
        "documentHash": "sha256:document",
        "renderSettingsHash": "sha256:settings",
        "profileId": "seznik-minix-s1-lyin48d-gy",
        "widthDots": 384,
        "heightDots": 240,
        "safety": {
            "allowed": True,
            "warnings": [],
            "metrics": {"totalBlackCoverage": 0.08, "maxBandCoverage64": 0.12},
        },
        "expiresAt": "2026-06-04T00:10:00.000Z",
        "message": "Preview created. User approval is required before printing.",
    }
    assert "approvalToken" not in response
    assert client.preview_calls == [
        (
            {"schemaVersion": 1, "target": {"profileId": "seznik-minix-s1-lyin48d-gy"}},
            {"threshold": 128},
        )
    ]


def test_print_note_builds_preview_document_and_requires_approval() -> None:
    client = StubDaemonClient()
    response = print_note_tool(client, text="Restock labels", title="Agent note")

    assert response["status"] == "approval_required"
    document, render_settings = client.preview_calls[0]
    assert document["title"] == "Agent note"
    assert document["target"] == {
        "profileId": "seznik-minix-s1-lyin48d-gy",
        "widthDots": 384,
        "heightDots": 160,
        "dpi": 203,
        "paperMode": "continuous",
        "density": "medium",
    }
    assert document["elements"] == [
        {
            "id": "text_note",
            "type": "text",
            "name": "Note text",
            "x": 12,
            "y": 12,
            "width": 360,
            "height": 136,
            "rotation": 0,
            "locked": False,
            "visible": True,
            "text": "Restock labels",
            "style": {"fill": "#000000", "fontFamily": "default", "fontSize": 12},
        }
    ]
    assert render_settings == {"threshold": 128, "dither": "none"}


def test_print_note_explains_agent_direct_policy_without_leaking_token() -> None:
    client = StubDaemonClient()

    response = print_note_tool(client, text="Restock labels", title="Agent note")

    assert response["status"] == "approval_required"
    assert response["policyDecision"] == {
        "tool": "print_note",
        "directPrintAllowed": False,
        "reasons": ["agent_direct_print_disabled", "printer_not_trusted"],
        "rateLimit": {"jobsPerMinute": 3},
    }
    assert response["safety"] == {
        "allowed": True,
        "warnings": [],
        "metrics": {"totalBlackCoverage": 0.08, "maxBandCoverage64": 0.12},
    }
    assert "approvalToken" not in str(response)


def test_get_job_status_returns_structured_daemon_job_without_raw_segments() -> None:
    response = get_job_status_tool(StubDaemonClient(), job_id="job_123")

    assert response == {
        "status": "ok",
        "job": {
            "jobId": "job_123",
            "state": "completed_unverified",
            "phase": "waiting_for_final_status",
            "completionLevel": "unverified",
            "completionConfidence": "mock_data_sent_final_ack_missing",
            "requiresUserCheck": True,
            "bandsSent": 2,
            "totalBands": 2,
            "safeActions": ["confirm_complete", "feed_paper", "reprint_from_start"],
        },
    }
    assert "approvalToken" not in str(response)
    assert "raster" not in str(response)


def test_tools_return_app_not_running_when_daemon_is_unavailable() -> None:
    client = StubDaemonClient(fail=True)

    assert get_daemon_status_tool(client)["status"] == "app_not_running"
    assert (
        preview_document_tool(client, document={}, render_settings={})["status"]
        == "app_not_running"
    )
    assert print_note_tool(client, text="hello")["status"] == "app_not_running"
    assert get_job_status_tool(client, job_id="job_123")["status"] == "app_not_running"
