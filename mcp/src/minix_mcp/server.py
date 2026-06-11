from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from mcp.server.fastmcp import FastMCP

from minix_mcp.daemon_client import DaemonHttpClient, JsonObject
from minix_mcp.runtime import resolve_daemon_runtime
from minix_mcp.tools import (
    DaemonClient,
    get_daemon_status_tool,
    get_job_status_tool,
    list_supported_profiles_tool,
    preview_document_tool,
    print_note_tool,
)

ClientFactory = Callable[[], DaemonClient]
AgentDirectUserOptInProvider = Callable[[], JsonObject | None]


def build_mcp_server(
    *,
    client_factory: ClientFactory | None = None,
    agent_direct_user_opt_in_provider: AgentDirectUserOptInProvider | None = None,
) -> FastMCP:
    factory = client_factory or build_default_client
    runtime_opt_in_provider = (
        agent_direct_user_opt_in_provider or build_default_agent_direct_user_opt_in
    )
    server = FastMCP(
        "MiniX Print Studio",
        instructions=(
            "Preview and request approval for MiniX thermal printer output. "
            "This server never exposes raw BLE access and never direct-prints by default."
        ),
    )

    @server.tool()
    def get_daemon_status() -> dict[str, Any]:
        """Check whether the MiniX Print Studio daemon is reachable."""
        return get_daemon_status_tool(factory())

    @server.tool()
    def get_job_status(job_id: str) -> dict[str, Any]:
        """Fetch a redacted daemon print job status by job id."""
        return get_job_status_tool(factory(), job_id=job_id)

    @server.tool()
    def list_supported_profiles() -> dict[str, Any]:
        """List supported printer profiles without low-level BLE or command payloads."""
        return list_supported_profiles_tool(factory())

    @server.tool()
    def preview_document(
        document: dict[str, Any],
        render_settings: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a daemon-canonical preview that requires user approval before printing."""
        return preview_document_tool(
            factory(),
            document=cast(JsonObject, document),
            render_settings=cast(JsonObject, render_settings),
        )

    @server.tool()
    def render_preview(
        document: dict[str, Any],
        render_settings: dict[str, Any],
    ) -> dict[str, Any]:
        """Render a daemon-canonical preview and return approval-required metadata."""
        return preview_document_tool(
            factory(),
            document=cast(JsonObject, document),
            render_settings=cast(JsonObject, render_settings),
        )

    @server.tool()
    def print_note(
        text: str,
        title: str = "Agent note",
        agent_direct_user_opt_in: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a preview for a short text note and require user approval before printing."""
        selected_agent_direct_user_opt_in = (
            cast(JsonObject, agent_direct_user_opt_in)
            if agent_direct_user_opt_in is not None
            else runtime_opt_in_provider()
        )
        return print_note_tool(
            factory(),
            text=text,
            title=title,
            agent_direct_user_opt_in=selected_agent_direct_user_opt_in,
        )

    return server


def build_default_client() -> DaemonHttpClient:
    runtime = resolve_daemon_runtime()
    return DaemonHttpClient(
        base_url=runtime.base_url,
        token=runtime.token,
    )


def build_default_agent_direct_user_opt_in() -> JsonObject | None:
    return resolve_daemon_runtime().agent_direct_user_opt_in


def run_stdio_server() -> None:
    build_mcp_server().run("stdio")
