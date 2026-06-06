from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def preview_safety_block_reason(safety: Mapping[str, Any]) -> str | None:
    if safety.get("allowed") is not False:
        return None

    error_codes = [
        code
        for error in safety.get("errors", [])
        if isinstance(error, Mapping) and isinstance(code := error.get("code"), str)
    ]
    reason = ", ".join(error_codes) if error_codes else "blocked_by_safety_policy"
    return f"preview safety blocked printing: {reason}"
