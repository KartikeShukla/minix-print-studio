from __future__ import annotations

import platform
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from minixd import __version__
from minixd.api.jobs import _serialize_print_job
from minixd.printing.queue import PrintJob, PrintQueue


class DiagnosticsExportRequest(BaseModel):
    include_project_content: bool = Field(default=False, alias="includeProjectContent")
    include_raw_images: bool = Field(default=False, alias="includeRawImages")


def create_diagnostics_router(
    *,
    profiles: list[dict[str, Any]],
    print_queue: PrintQueue,
    mock: bool,
    profile_registry_version: str,
) -> APIRouter:
    router = APIRouter(prefix="/v1/diagnostics", tags=["diagnostics"])

    @router.post("/export")
    def export_diagnostics(request: DiagnosticsExportRequest) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "createdAt": datetime.now(UTC).isoformat(),
            "redaction": {
                "projectContentIncluded": request.include_project_content,
                "rawImagesIncluded": request.include_raw_images,
                "tokensIncluded": False,
            },
            "daemon": {
                "version": __version__,
                "profileRegistryVersion": profile_registry_version,
                "mock": mock,
                "os": platform.system(),
                "python": platform.python_version(),
            },
            "profiles": [_profile_snapshot(profile) for profile in profiles],
            "jobs": [_job_diagnostics(job, print_queue) for job in print_queue.list_jobs()],
            "recentErrors": [],
            "recentMcpCalls": [],
        }

    return router


def _profile_snapshot(profile: dict[str, Any]) -> dict[str, object]:
    print_config = _dict_value(profile, "print")
    long_print = _dict_value(print_config, "longPrint")
    safety = _dict_value(profile, "safety")
    ble = _dict_value(profile, "ble")
    return {
        "id": _string_or_none(profile.get("id")),
        "displayName": _string_or_none(profile.get("displayName")),
        "supportLevel": _string_or_none(profile.get("supportLevel")),
        "profileVersion": _string_or_none(profile.get("profileVersion")),
        "modelResponse": _string_or_none(profile.get("modelResponse")),
        "observedFirmware": _string_list(profile.get("observedFirmware")),
        "ble": {
            "serviceUuid": _string_or_none(ble.get("serviceUuid")),
            "writeCharUuid": _string_or_none(ble.get("writeCharUuid")),
            "notifyCharUuids": _string_list(ble.get("notifyCharUuids")),
        },
        "print": {
            "protocol": _string_or_none(print_config.get("protocol")),
            "widthDots": print_config.get("widthDots"),
            "rowBytes": print_config.get("rowBytes"),
            "defaultPaperMode": _string_or_none(print_config.get("defaultPaperMode")),
            "defaultDensity": _string_or_none(print_config.get("defaultDensity")),
            "longPrint": {
                "transferMode": _string_or_none(long_print.get("transferMode")),
                "defaultMaxBandHeightDots": long_print.get("defaultMaxBandHeightDots"),
                "appendTailBlankRowsContinuous": long_print.get(
                    "appendTailBlankRowsContinuous"
                ),
                "finalAckPolicy": _string_or_none(long_print.get("finalAckPolicy")),
            },
        },
        "safety": {
            "maxHeightDotsManual": safety.get("maxHeightDotsManual"),
            "maxHeightDotsAgentDirect": safety.get("maxHeightDotsAgentDirect"),
            "maxCopiesAgentDirect": safety.get("maxCopiesAgentDirect"),
            "warnTotalBlackCoverage": safety.get("warnTotalBlackCoverage"),
            "blockAgentTotalBlackCoverage": safety.get("blockAgentTotalBlackCoverage"),
            "blockBandCoverage": safety.get("blockBandCoverage"),
        },
    }


def _job_diagnostics(job: PrintJob, print_queue: PrintQueue) -> dict[str, object]:
    serialized = _serialize_print_job(job)
    serialized["segments"] = [
        {
            "index": segment.index,
            "startRow": segment.start_row,
            "heightDots": segment.height_dots,
            "rasterByteOffset": segment.raster_byte_offset,
            "rasterByteLength": segment.raster_byte_length,
            "payloadBytes": segment.payload_bytes,
            "sha256": segment.sha256,
        }
        for segment in print_queue.get_segments(job.job_id)
    ]
    serialized["completionDecision"] = {
        "level": job.completion_level,
        "confidence": job.completion_confidence,
        "phase": job.phase,
        "requiresUserCheck": job.requires_user_check,
        "explanation": "Mock transport sent all planned bands but cannot verify physical output.",
    }
    serialized["timing"] = {
        "bleWrites": {"summary": "not captured in mock transport"},
        "notifications": {"summary": "not captured in mock transport"},
    }
    return serialized


def _dict_value(value: dict[str, Any], key: str) -> dict[str, Any]:
    child = value.get(key)
    return child if isinstance(child, dict) else {}


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _string_list(value: object) -> list[str]:
    return [item for item in value] if isinstance(value, list) and all(
        isinstance(item, str) for item in value
    ) else []
