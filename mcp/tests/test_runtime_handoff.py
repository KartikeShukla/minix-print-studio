import json

import pytest

from minix_mcp.runtime import resolve_daemon_runtime


def test_resolves_daemon_runtime_from_electron_handoff_file(tmp_path) -> None:
    token_file = tmp_path / "token"
    runtime_file = tmp_path / "runtime.json"
    token_file.write_text("token_private\n", encoding="utf-8")
    runtime_file.write_text(
        json.dumps(
            {
                "version": 1,
                "pid": 12345,
                "baseUrl": "http://127.0.0.1:43210",
                "tokenFile": str(token_file),
                "startedAt": "2026-06-04T10:00:00.000Z",
            }
        ),
        encoding="utf-8",
    )

    runtime = resolve_daemon_runtime({"MINIX_DAEMON_RUNTIME_FILE": str(runtime_file)})

    assert runtime.base_url == "http://127.0.0.1:43210"
    assert runtime.token == "token_private"
    assert runtime.agent_direct_user_opt_in is None


def test_resolves_agent_direct_user_opt_in_from_runtime_handoff_file(tmp_path) -> None:
    token_file = tmp_path / "token"
    gate_file = tmp_path / "agent-direct-user-opt-in.json"
    runtime_file = tmp_path / "runtime.json"
    token_file.write_text("token_private\n", encoding="utf-8")
    gate = _agent_direct_user_opt_in_record()
    gate_file.write_text(json.dumps(gate), encoding="utf-8")
    runtime_file.write_text(
        json.dumps(
            {
                "version": 1,
                "pid": 12345,
                "baseUrl": "http://127.0.0.1:43210",
                "tokenFile": str(token_file),
                "agentDirectUserOptInFile": str(gate_file),
                "startedAt": "2026-06-04T10:00:00.000Z",
            }
        ),
        encoding="utf-8",
    )

    runtime = resolve_daemon_runtime({"MINIX_DAEMON_RUNTIME_FILE": str(runtime_file)})

    assert runtime.base_url == "http://127.0.0.1:43210"
    assert runtime.token == "token_private"
    assert runtime.agent_direct_user_opt_in == gate


def test_resolve_daemon_runtime_rejects_runtime_file_with_inline_token(tmp_path) -> None:
    runtime_file = tmp_path / "runtime.json"
    runtime_file.write_text(
        json.dumps(
            {
                "version": 1,
                "baseUrl": "http://127.0.0.1:43210",
                "token": "inline-secret",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="tokenFile"):
        resolve_daemon_runtime({"MINIX_DAEMON_RUNTIME_FILE": str(runtime_file)})


def test_resolve_daemon_runtime_rejects_inline_agent_direct_user_opt_in(
    tmp_path,
) -> None:
    token_file = tmp_path / "token"
    runtime_file = tmp_path / "runtime.json"
    token_file.write_text("token_private\n", encoding="utf-8")
    runtime_file.write_text(
        json.dumps(
            {
                "version": 1,
                "baseUrl": "http://127.0.0.1:43210",
                "tokenFile": str(token_file),
                "agentDirectUserOptIn": _agent_direct_user_opt_in_record(),
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="agentDirectUserOptInFile"):
        resolve_daemon_runtime({"MINIX_DAEMON_RUNTIME_FILE": str(runtime_file)})


def _agent_direct_user_opt_in_record() -> dict[str, object]:
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
