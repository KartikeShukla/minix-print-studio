from __future__ import annotations

import base64
import binascii
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from minixd.printing.planner import PrintPlanPackage, create_print_plan


class PlanJobRequest(BaseModel):
    job_id: Annotated[str, Field(alias="jobId", min_length=1)]
    preview_id: Annotated[str, Field(alias="previewId", min_length=1)]
    document_hash: Annotated[str, Field(alias="documentHash", min_length=1)]
    profile_id: Annotated[str, Field(alias="profileId", min_length=1)]
    paper_mode: Annotated[
        str, Field(alias="paperMode", pattern="^(continuous|gap_label|black_mark)$")
    ]
    density: Annotated[str, Field(pattern="^(light|medium|dark)$")]
    content_height_dots: Annotated[int, Field(alias="contentHeightDots", gt=0)]
    content_raster_base64: Annotated[str, Field(alias="contentRasterBase64", min_length=1)]


def create_jobs_router(*, profiles: list[dict[str, Any]]) -> APIRouter:
    router = APIRouter(prefix="/v1/jobs", tags=["jobs"])

    @router.post("/plan")
    def plan_job(request: PlanJobRequest) -> dict[str, object]:
        profile = _find_profile(profiles, request.profile_id)
        content_raster = _decode_base64(request.content_raster_base64)
        package = create_print_plan(
            job_id=request.job_id,
            preview_id=request.preview_id,
            document_hash=request.document_hash,
            content_raster=content_raster,
            content_height_dots=request.content_height_dots,
            profile=profile,
            paper_mode=request.paper_mode,
            density=request.density,
        )
        return _serialize_plan_package(package)

    return router


def _find_profile(profiles: list[dict[str, Any]], profile_id: str) -> dict[str, Any]:
    for profile in profiles:
        if profile.get("id") == profile_id:
            return profile
    raise HTTPException(status_code=404, detail=f"unknown profile: {profile_id}")


def _decode_base64(value: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="contentRasterBase64 is invalid") from exc


def _serialize_plan_package(package: PrintPlanPackage) -> dict[str, object]:
    return {
        "plan": {
            "planId": package.plan.plan_id,
            "jobId": package.plan.job_id,
            "previewId": package.plan.preview_id,
            "documentHash": package.plan.document_hash,
            "rasterHash": package.plan.raster_hash,
            "profileId": package.plan.profile_id,
            "paperMode": package.plan.paper_mode,
            "density": package.plan.density,
            "widthDots": package.plan.width_dots,
            "contentHeightDots": package.plan.content_height_dots,
            "tailBlankRowsDots": package.plan.tail_blank_rows_dots,
            "transferHeightDots": package.plan.transfer_height_dots,
            "rowBytes": package.plan.row_bytes,
            "totalRasterBytes": package.plan.total_raster_bytes,
            "requiresLongPrintMode": package.plan.requires_long_print_mode,
        },
        "totalBands": len(package.bands),
        "bands": [
            {
                "index": band.index,
                "startRow": band.start_row,
                "heightDots": band.height_dots,
                "rasterByteOffset": band.raster_byte_offset,
                "rasterByteLength": band.raster_byte_length,
                "payloadBytes": band.payload_bytes,
                "sha256": band.sha256,
            }
            for band in package.bands
        ],
    }
