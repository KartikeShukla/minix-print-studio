from __future__ import annotations

import json
import platform
from datetime import UTC, datetime
from io import BytesIO
from typing import Any, Literal
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from minixd import __version__
from minixd.api.jobs import _serialize_print_job
from minixd.ble.discovery import (
    PrinterDiscoveryError,
    PrinterDiscoveryService,
    PrinterNotFoundError,
    ReadOnlyVerification,
)
from minixd.printing.queue import PrintJob, PrintQueue


class DiagnosticsExportRequest(BaseModel):
    include_project_content: bool = Field(default=False, alias="includeProjectContent")
    include_raw_images: bool = Field(default=False, alias="includeRawImages")


class HardwareTestRequest(BaseModel):
    device_id: str = Field(alias="deviceId", min_length=1)
    stage: Literal["read_only_verification"] = "read_only_verification"
    user_confirmation: dict[str, Any] = Field(default_factory=dict, alias="userConfirmation")


def create_diagnostics_router(
    *,
    profiles: list[dict[str, Any]],
    print_queue: PrintQueue,
    discovery_service: PrinterDiscoveryService,
    mock: bool,
    profile_registry_version: str,
) -> APIRouter:
    router = APIRouter(prefix="/v1/diagnostics", tags=["diagnostics"])

    @router.post("/export")
    def export_diagnostics(request: DiagnosticsExportRequest) -> dict[str, object]:
        return _build_diagnostics_bundle(
            request=request,
            profiles=profiles,
            print_queue=print_queue,
            mock=mock,
            profile_registry_version=profile_registry_version,
        )

    @router.post("/export/archive")
    def export_diagnostics_archive(request: DiagnosticsExportRequest) -> Response:
        bundle = _build_diagnostics_bundle(
            request=request,
            profiles=profiles,
            print_queue=print_queue,
            mock=mock,
            profile_registry_version=profile_registry_version,
        )
        archive = BytesIO()
        with ZipFile(archive, "w", ZIP_DEFLATED) as diagnostics_zip:
            diagnostics_zip.writestr("diagnostics.json", json.dumps(bundle, indent=2))
            diagnostics_zip.writestr(
                "README.md",
                "MiniX Print Studio diagnostics export. Raw raster bytes, approval tokens, "
                "and project content are excluded unless explicitly marked in diagnostics.json.\n",
            )
        return Response(
            content=archive.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="minix-diagnostics.zip"'},
        )

    @router.post("/hardware-test")
    async def export_hardware_test(request: HardwareTestRequest) -> Response:
        try:
            verification = await discovery_service.read_only_verify(request.device_id)
        except PrinterNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PrinterDiscoveryError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        archive = _build_read_only_hardware_test_archive(
            request=request,
            verification=verification,
            profiles=profiles,
            mock=mock,
            profile_registry_version=profile_registry_version,
        )
        created_at = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        return Response(
            content=archive,
            media_type="application/zip",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="hardware-test-{created_at}.zip"'
                )
            },
        )

    return router


def _build_diagnostics_bundle(
    *,
    request: DiagnosticsExportRequest,
    profiles: list[dict[str, Any]],
    print_queue: PrintQueue,
    mock: bool,
    profile_registry_version: str,
) -> dict[str, object]:
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
        "explanation": _completion_explanation(job),
    }
    serialized["timing"] = {
        "bleWrites": {"summary": "not captured in mock transport"},
        "notifications": {"summary": "not captured in mock transport"},
    }
    return serialized


def _completion_explanation(job: PrintJob) -> str:
    prefix = "mock_disconnect_after_band_"
    if job.completion_confidence.startswith(prefix):
        band_index = job.completion_confidence.removeprefix(prefix)
        if job.completion_level == "failed_partial_output":
            return (
                f"Mock transport disconnected after band {band_index}; printable bytes may "
                "have left the printer. Do not auto-retry."
            )
        return (
            f"Mock transport disconnected before printable output after band {band_index}; "
            "retry from the start is allowed."
        )
    return "Mock transport sent all planned bands but cannot verify physical output."


def _build_read_only_hardware_test_archive(
    *,
    request: HardwareTestRequest,
    verification: ReadOnlyVerification,
    profiles: list[dict[str, Any]],
    mock: bool,
    profile_registry_version: str,
) -> bytes:
    matching_profile = _find_profile(profiles, verification.profile_id)
    transfer_manifest = {
        "stage": request.stage,
        "deviceId": verification.device_id,
        "profileId": verification.profile_id,
        "printCommandsSent": False,
        "rasterBytesIncluded": False,
        "printable": verification.printable,
        "nextRequiredStage": verification.next_required_stage,
        "reason": verification.reason,
    }
    archive = BytesIO()
    with ZipFile(archive, "w", ZIP_DEFLATED) as hardware_zip:
        hardware_zip.writestr(
            "device.json",
            _json_bytes(
                {
                    "deviceId": verification.device_id,
                    "status": verification.status,
                    "profileId": verification.profile_id,
                    "profileSupportLevel": verification.profile_support_level,
                    "modelResponse": verification.model_response,
                    "firmware": verification.firmware,
                    "printable": verification.printable,
                    "nextRequiredStage": verification.next_required_stage,
                    "reason": verification.reason,
                }
            ),
        )
        hardware_zip.writestr(
            "profile.json",
            _json_bytes(_profile_snapshot(matching_profile) if matching_profile else {}),
        )
        hardware_zip.writestr(
            "ble-discovery.json",
            _json_bytes(
                {
                    "services": verification.services,
                    "writeCharacteristics": verification.write_characteristics,
                    "notifyCharacteristics": verification.notify_characteristics,
                    "rawNotificationCount": len(verification.raw_notifications),
                    "timingEvents": [
                        {
                            "operation": event.operation,
                            "characteristic": event.characteristic,
                            "elapsedMs": event.elapsed_ms,
                            "payloadBytes": event.payload_bytes,
                        }
                        for event in verification.timing_events
                    ],
                }
            ),
        )
        hardware_zip.writestr(
            "model-response.bin",
            (verification.model_response or "").encode("utf-8"),
        )
        hardware_zip.writestr(
            "firmware-response.bin",
            (verification.firmware or "").encode("utf-8"),
        )
        hardware_zip.writestr(
            "notifications.log",
            "\n".join(verification.raw_notifications).encode("utf-8"),
        )
        hardware_zip.writestr("commands.log", _commands_log(verification))
        hardware_zip.writestr("print-transfer-manifest.json", _json_bytes(transfer_manifest))
        hardware_zip.writestr(
            "band-manifest.json",
            _json_bytes(
                {
                    "bands": [],
                    "notApplicableReason": (
                        "Read-only verification does not send raster bands."
                    ),
                }
            ),
        )
        hardware_zip.writestr(
            "finalizer-result.json",
            _json_bytes(
                {
                    "status": "not_applicable",
                    "reason": "Read-only verification does not run print finalizers.",
                }
            ),
        )
        hardware_zip.writestr(
            "safety-report.json",
            _json_bytes(
                {
                    "printingLocked": True,
                    "certificationComplete": False,
                    "certificationStage": request.stage,
                    "nextRequiredStage": verification.next_required_stage,
                    "reason": "Read-only verification alone never unlocks printing.",
                }
            ),
        )
        hardware_zip.writestr(
            "user-confirmation.json",
            _json_bytes(
                {
                    "stage": request.stage,
                    "responses": request.user_confirmation,
                    "requiredForCertification": True,
                    "certificationComplete": False,
                }
            ),
        )
        hardware_zip.writestr(
            "app-version.json",
            _json_bytes(
                {
                    "daemonVersion": __version__,
                    "profileRegistryVersion": profile_registry_version,
                    "mock": mock,
                    "os": platform.system(),
                    "python": platform.python_version(),
                }
            ),
        )
        hardware_zip.writestr(
            "README.md",
            (
                "MiniX Print Studio hardware-test artifact for Stage A read-only "
                "verification. This archive does not certify the printer and does not "
                "include raster bytes, approval tokens, or print commands.\n"
            ),
        )
    return archive.getvalue()


def _find_profile(profiles: list[dict[str, Any]], profile_id: str | None) -> dict[str, Any] | None:
    if profile_id is None:
        return None
    for profile in profiles:
        if profile.get("id") == profile_id:
            return profile
    return None


def _commands_log(verification: ReadOnlyVerification) -> bytes:
    lines = [
        json.dumps(
            {
                "operation": event.operation,
                "characteristic": event.characteristic,
                "elapsedMs": event.elapsed_ms,
                "payloadBytes": event.payload_bytes,
                "rawPayloadIncluded": False,
            },
            sort_keys=True,
        )
        for event in verification.timing_events
        if event.operation == "write_gatt_char"
    ]
    return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, indent=2, sort_keys=True).encode("utf-8")


def _dict_value(value: dict[str, Any], key: str) -> dict[str, Any]:
    child = value.get(key)
    return child if isinstance(child, dict) else {}


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _string_list(value: object) -> list[str]:
    return [item for item in value] if isinstance(value, list) and all(
        isinstance(item, str) for item in value
    ) else []
