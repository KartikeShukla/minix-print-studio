from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

from mcp import ClientSession, StdioServerParameters, stdio_client

from minix_mcp.daemon_client import JsonObject


async def run_mcp_stdio_smoke(
    *,
    command: str,
    args: Sequence[str] = (),
    env: Mapping[str, str] | None = None,
) -> JsonObject:
    server = StdioServerParameters(
        command=command,
        args=list(args),
        env=dict(env) if env is not None else None,
    )

    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            response = await session.call_tool("get_daemon_status", {})

    if response.structuredContent is None:
        raise RuntimeError("MCP stdio smoke returned no structured content")

    return cast(JsonObject, response.structuredContent)
