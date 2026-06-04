from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from minixd.ble.discovery import (
    PrinterCandidate,
    PrinterDiscoveryError,
    PrinterDiscoveryService,
    PrinterNotFoundError,
    ReadOnlyVerification,
)


class ReadOnlyVerifyRequest(BaseModel):
    device_id: Annotated[str, Field(alias="deviceId", min_length=1)]


def create_printers_router(*, discovery_service: PrinterDiscoveryService) -> APIRouter:
    router = APIRouter(prefix="/v1/printers", tags=["printers"])

    @router.get("/scan")
    @router.post("/scan")
    async def scan_printers() -> dict[str, list[dict[str, object]]]:
        return {
            "printers": [
                _serialize_candidate(candidate)
                for candidate in await discovery_service.scan()
            ]
        }

    @router.post("/read-only-verify")
    async def read_only_verify(request: ReadOnlyVerifyRequest) -> dict[str, object]:
        try:
            verification = await discovery_service.read_only_verify(request.device_id)
        except PrinterNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PrinterDiscoveryError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _serialize_verification(verification)

    return router


def _serialize_candidate(candidate: PrinterCandidate) -> dict[str, object]:
    return {
        "deviceId": candidate.device_id,
        "name": candidate.name,
        "serviceUuids": candidate.service_uuids,
        "rssi": candidate.rssi,
        "supportLevel": candidate.support_level,
        "candidateProfileIds": candidate.candidate_profile_ids,
        "printable": candidate.printable,
        "nextRequiredStage": candidate.next_required_stage,
        "reason": candidate.reason,
    }


def _serialize_verification(verification: ReadOnlyVerification) -> dict[str, object]:
    return {
        "status": verification.status,
        "deviceId": verification.device_id,
        "profileId": verification.profile_id,
        "profileSupportLevel": verification.profile_support_level,
        "modelResponse": verification.model_response,
        "firmware": verification.firmware,
        "printable": verification.printable,
        "nextRequiredStage": verification.next_required_stage,
        "reason": verification.reason,
        "services": verification.services,
        "writeCharacteristics": verification.write_characteristics,
        "notifyCharacteristics": verification.notify_characteristics,
        "rawNotifications": verification.raw_notifications,
    }
