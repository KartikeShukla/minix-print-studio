from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from minix_mcp.daemon_client import JsonObject


@dataclass(frozen=True)
class DaemonRuntime:
    base_url: str
    token: str
    agent_direct_user_opt_in: JsonObject | None = None


def resolve_daemon_runtime(env: Mapping[str, str] | None = None) -> DaemonRuntime:
    values = os.environ if env is None else env
    direct_base_url = values.get("MINIX_DAEMON_BASE_URL")
    direct_token = values.get("MINIX_DAEMON_TOKEN")
    if direct_base_url and direct_token:
        return DaemonRuntime(base_url=direct_base_url, token=direct_token)

    runtime_file = values.get("MINIX_DAEMON_RUNTIME_FILE")
    if runtime_file:
        return _read_runtime_file(Path(runtime_file))

    return DaemonRuntime(base_url="http://127.0.0.1:39281", token="dev-token")


def _read_runtime_file(runtime_file: Path) -> DaemonRuntime:
    raw = json.loads(runtime_file.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("daemon runtime file must contain an object")

    data: dict[str, Any] = raw
    if "token" in data:
        raise ValueError("daemon runtime file must reference tokenFile, not an inline token")
    if "agentDirectUserOptIn" in data:
        raise ValueError(
            "daemon runtime file must reference agentDirectUserOptInFile, "
            "not inline agentDirectUserOptIn"
        )

    base_url = data.get("baseUrl")
    token_file = data.get("tokenFile")
    agent_direct_user_opt_in_file = data.get("agentDirectUserOptInFile")
    if not isinstance(base_url, str) or not base_url:
        raise ValueError("daemon runtime file is missing baseUrl")
    if not isinstance(token_file, str) or not token_file:
        raise ValueError("daemon runtime file is missing tokenFile")
    if agent_direct_user_opt_in_file is not None and (
        not isinstance(agent_direct_user_opt_in_file, str)
        or not agent_direct_user_opt_in_file
    ):
        raise ValueError("daemon runtime file has invalid agentDirectUserOptInFile")

    token = Path(token_file).read_text(encoding="utf-8").strip()
    if not token:
        raise ValueError("daemon token file is empty")

    agent_direct_user_opt_in = (
        _read_agent_direct_user_opt_in_file(
            runtime_file,
            agent_direct_user_opt_in_file,
        )
        if agent_direct_user_opt_in_file is not None
        else None
    )

    return DaemonRuntime(
        base_url=base_url,
        token=token,
        agent_direct_user_opt_in=agent_direct_user_opt_in,
    )


def _read_agent_direct_user_opt_in_file(
    runtime_file: Path,
    agent_direct_user_opt_in_file: str,
) -> JsonObject:
    gate_path = Path(agent_direct_user_opt_in_file)
    if not gate_path.is_absolute():
        gate_path = runtime_file.parent / gate_path
    raw = json.loads(gate_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("agentDirectUserOptInFile must contain an object")
    return raw
