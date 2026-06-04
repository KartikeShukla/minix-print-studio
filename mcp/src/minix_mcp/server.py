from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from mcp.server.fastmcp import FastMCP

from minix_mcp.daemon_client import DaemonHttpClient, JsonObject
from minix_mcp.runtime import resolve_daemon_runtime
from minix_mcp.tools import (
    DaemonClient,
    get_daemon_status_tool,
    preview_document_tool,
    print_note_tool,
)

ClientFactory = Callable[[], DaemonClient]


def build_mcp_server(
    *,
    client_factory: ClientFactory | None = None,
) -> FastMCP:
    factory = client_factory or build_default_client
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
    def print_note(
        text: str,
        title: str = "Agent note",
    ) -> dict[str, Any]:
        """Create a preview for a short text note and require user approval before printing."""
        return print_note_tool(factory(), text=text, title=title)

    return server


def build_default_client() -> DaemonHttpClient:
    runtime = resolve_daemon_runtime()
    return DaemonHttpClient(
        base_url=runtime.base_url,
        token=runtime.token,
    )


def run_stdio_server() -> None:
    build_mcp_server().run("stdio")
