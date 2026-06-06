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
        "preview_document",
        "print_note",
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
async def test_mcp_server_calls_get_job_status_tool(
    client_session: ClientSession,
) -> None:
    result = await client_session.call_tool("get_job_status", {"job_id": "job_123"})

    assert result.structuredContent is not None
    assert result.structuredContent["status"] == "ok"
    assert result.structuredContent["job"]["jobId"] == "job_123"
    assert result.structuredContent["job"]["completionLevel"] == "unverified"
