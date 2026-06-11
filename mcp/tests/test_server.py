from collections.abc import AsyncGenerator

import pytest
from mcp.client.session import ClientSession
from mcp.shared.memory import create_connected_server_and_client_session

from minix_mcp.daemon_client import JsonObject
from minix_mcp.server import build_mcp_server


class StubDaemonClient:
    def get_health(self) -> JsonObject:
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
        return {
            "previewId": "prev_stdio",
            "approvalToken": "appr_hidden",
            "documentHash": "sha256:document",
            "renderSettingsHash": "sha256:settings",
            "profileId": "seznik-minix-s1-lyin48d-gy",
            "widthDots": 384,
            "heightDots": 200,
            "expiresAt": "2026-06-04T00:10:00.000Z",
        }

    def get_job_status(self, job_id: str) -> JsonObject:
        return {
            "jobId": job_id,
            "state": "completed_unverified",
            "completionLevel": "unverified",
            "requiresUserCheck": True,
            "safeActions": ["confirm_complete"],
        }

    def get_profiles(self) -> JsonObject:
        return {
            "profiles": [
                {
                    "id": "seznik-minix-s1-lyin48d-gy",
                    "displayName": "Seznik MiniX - S1_LYiN48D_GY",
                    "supportLevel": "official",
                    "profileVersion": "1.0.0",
                    "print": {"widthDots": 384, "rowBytes": 48},
                }
            ]
        }


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client_session() -> AsyncGenerator[ClientSession]:
    server = build_mcp_server(client_factory=StubDaemonClient)
    async with create_connected_server_and_client_session(
        server,
        raise_exceptions=True,
    ) as session:
        yield session


@pytest.mark.anyio
async def test_mcp_server_lists_minix_tools(client_session: ClientSession) -> None:
    tools = await client_session.list_tools()

    assert {tool.name for tool in tools.tools} == {
        "get_daemon_status",
        "get_job_status",
        "list_supported_profiles",
        "preview_document",
        "print_note",
        "render_preview",
    }


@pytest.mark.anyio
async def test_mcp_server_calls_daemon_status_tool(client_session: ClientSession) -> None:
    result = await client_session.call_tool("get_daemon_status", {})

    assert result.structuredContent is not None
    assert result.structuredContent["status"] == "ok"
    assert result.structuredContent["daemon"]["mock"] is True


@pytest.mark.anyio
async def test_mcp_server_calls_preview_document_without_exposing_token(
    client_session: ClientSession,
) -> None:
    result = await client_session.call_tool(
        "preview_document",
        {
            "document": {
                "schemaVersion": 1,
                "target": {"profileId": "seznik-minix-s1-lyin48d-gy"},
            },
            "render_settings": {"threshold": 128},
        },
    )

    assert result.structuredContent is not None
    assert result.structuredContent["status"] == "approval_required"
    assert result.structuredContent["previewId"] == "prev_stdio"
    assert "approvalToken" not in result.structuredContent


@pytest.mark.anyio
async def test_mcp_server_calls_render_preview_tool(
    client_session: ClientSession,
) -> None:
    result = await client_session.call_tool(
        "render_preview",
        {
            "document": {
                "schemaVersion": 1,
                "target": {"profileId": "seznik-minix-s1-lyin48d-gy"},
            },
            "render_settings": {"threshold": 128},
        },
    )

    assert result.structuredContent is not None
    assert result.structuredContent["status"] == "approval_required"
    assert result.structuredContent["previewId"] == "prev_stdio"
    assert "approvalToken" not in result.structuredContent


@pytest.mark.anyio
async def test_mcp_server_calls_print_note_with_agent_direct_opt_in(
    client_session: ClientSession,
) -> None:
    result = await client_session.call_tool(
        "print_note",
        {
            "text": "Restock labels",
            "title": "Agent note",
            "agent_direct_user_opt_in": _agent_direct_user_opt_in_record(),
        },
    )

    assert result.structuredContent is not None
    assert result.structuredContent["status"] == "approval_required"
    assert result.structuredContent["policyDecision"]["directPrintAllowed"] is True
    assert (
        result.structuredContent["policyDecision"]["runtimeApprovalRequired"] is True
    )
    assert (
        result.structuredContent["policyDecision"]["unattendedPrintingAllowed"] is False
    )
    assert "approvalToken" not in str(result.structuredContent)


@pytest.mark.anyio
async def test_mcp_server_uses_runtime_selected_agent_direct_opt_in() -> None:
    server = build_mcp_server(
        client_factory=StubDaemonClient,
        agent_direct_user_opt_in_provider=_agent_direct_user_opt_in_record,
    )
    async with create_connected_server_and_client_session(
        server,
        raise_exceptions=True,
    ) as session:
        result = await session.call_tool(
            "print_note",
            {
                "text": "Restock labels",
                "title": "Agent note",
            },
        )

    assert result.structuredContent is not None
    assert result.structuredContent["status"] == "approval_required"
    assert result.structuredContent["policyDecision"]["directPrintAllowed"] is True
    assert (
        result.structuredContent["policyDecision"]["sourceGate"]
        == "agent_direct_user_opt_in"
    )
    assert "approvalToken" not in str(result.structuredContent)


@pytest.mark.anyio
async def test_mcp_server_calls_get_job_status_tool(
    client_session: ClientSession,
) -> None:
    result = await client_session.call_tool("get_job_status", {"job_id": "job_123"})

    assert result.structuredContent is not None
    assert result.structuredContent["status"] == "ok"
    assert result.structuredContent["job"]["jobId"] == "job_123"
    assert result.structuredContent["job"]["completionLevel"] == "unverified"


@pytest.mark.anyio
async def test_mcp_server_calls_list_supported_profiles_tool(
    client_session: ClientSession,
) -> None:
    result = await client_session.call_tool("list_supported_profiles", {})

    assert result.structuredContent is not None
    assert result.structuredContent["status"] == "ok"
    assert result.structuredContent["profiles"][0]["id"] == "seznik-minix-s1-lyin48d-gy"
    assert "serviceUuid" not in str(result.structuredContent)


def _agent_direct_user_opt_in_record() -> JsonObject:
    return {
        "status": "agent_direct_user_opt_in_recorded",
        "sourcePolicyReview": {
            "stage": "agent_direct_policy_review",
            "status": "agent_direct_policy_reviewed",
            "localRecordValidated": True,
        },
        "optIn": {
            "explicitUserOptIn": True,
            "recordedVia": "local_cli_confirmation",
            "directPrintDefault": "approval_required",
            "unattendedPrintingAllowed": False,
        },
        "agentRules": {
            "directPrintEnabled": True,
            "directPrintDefault": "approval_required",
            "approvalRequiredByDefault": True,
            "longDirectPrintRequiresApproval": True,
            "overLimitBehavior": "preview_and_ask",
            "noAutomaticRetryAfterPrintableBytes": True,
            "rawBleWritesAllowed": False,
            "unsafeResumeAllowed": False,
            "requiresTrustedPrinter": True,
            "requiresStableSupportGate": True,
        },
        "limits": {
            "maxHeightDots": 1000,
            "warnTotalBlackCoverage": 0.3,
            "blockTotalBlackCoverage": 0.45,
            "blockBandCoverage": 0.7,
            "maxCopies": 1,
            "jobsPerMinute": 3,
        },
        "safety": {
            "stableSupportClaimEnabled": True,
            "longPrintPrintingEnabled": True,
            "agentDirectPrintingEnabled": True,
            "agentDirectPrintingDefault": "approval_required",
            "unattendedAgentPrintingEnabled": False,
        },
        "nextRequiredStage": "runtime_approval_enforcement",
    }
