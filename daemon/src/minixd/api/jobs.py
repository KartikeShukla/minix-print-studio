from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from minixd.printing.planner import PrintPlanPackage, create_print_plan
from minixd.printing.queue import PrintJob, PrintQueue, PrintRejectedError
from minixd.printing.safety import preview_safety_block_reason
from minixd.render.preview_store import PreviewBindingError, PreviewStore


class PlanJobRequest(BaseModel):
    job_id: Annotated[str, Field(alias="jobId", min_length=1)]
    preview_id: Annotated[str, Field(alias="previewId", min_length=1)]
    approval_token: Annotated[str, Field(alias="approvalToken", min_length=1)]
    document_hash: Annotated[str, Field(alias="documentHash", min_length=1)]
    render_settings_hash: Annotated[str, Field(alias="renderSettingsHash", min_length=1)]
    profile_id: Annotated[str, Field(alias="profileId", min_length=1)]
    paper_mode: Annotated[
        str, Field(alias="paperMode", pattern="^(continuous|gap_label|black_mark)$")
    ]
    density: Annotated[str, Field(pattern="^(light|medium|dark)$")]


class PrintJobRequest(BaseModel):
    preview_id: Annotated[str, Field(alias="previewId", min_length=1)]
    approval_token: Annotated[str, Field(alias="approvalToken", min_length=1)]
    document_hash: Annotated[str, Field(alias="documentHash", min_length=1)]
    render_settings_hash: Annotated[str, Field(alias="renderSettingsHash", min_length=1)]
    profile_id: Annotated[str, Field(alias="profileId", min_length=1)]
    paper_mode: Annotated[
        str, Field(alias="paperMode", pattern="^(continuous|gap_label|black_mark)$")
    ]
    density: Annotated[str, Field(pattern="^(light|medium|dark)$")]
    copies: Annotated[int, Field(gt=0, le=5)]
    source: Annotated[str, Field(min_length=1)]


def create_jobs_router(
    *,
    profiles: list[dict[str, Any]],
    preview_store: PreviewStore,
    print_queue: PrintQueue,
) -> APIRouter:
    router = APIRouter(prefix="/v1/jobs", tags=["jobs"])

    @router.post("/plan")
    def plan_job(request: PlanJobRequest) -> dict[str, object]:
        profile = _find_profile(profiles, request.profile_id)
        try:
            preview = preview_store.verify(
                preview_id=request.preview_id,
                approval_token=request.approval_token,
                document_hash=request.document_hash,
                render_settings_hash=request.render_settings_hash,
            )
        except PreviewBindingError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        if block_reason := preview_safety_block_reason(preview.safety):
            raise HTTPException(status_code=409, detail=block_reason)

        package = create_print_plan(
            job_id=request.job_id,
            preview_id=preview.preview_id,
            document_hash=request.document_hash,
            content_raster=preview.raster,
            content_height_dots=preview.height_dots,
            profile=profile,
            paper_mode=request.paper_mode,
            density=request.density,
        )
        return _serialize_plan_package(package)

    @router.post("/print")
    def print_job(request: PrintJobRequest) -> dict[str, object]:
        try:
            job = print_queue.print_preview(
                preview_id=request.preview_id,
                approval_token=request.approval_token,
                document_hash=request.document_hash,
                render_settings_hash=request.render_settings_hash,
                profile_id=request.profile_id,
                paper_mode=request.paper_mode,
                density=request.density,
                copies=request.copies,
                source=request.source,
            )
        except PrintRejectedError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _serialize_print_job(job)

    @router.get("")
    def list_jobs() -> dict[str, list[dict[str, object]]]:
        return {"jobs": [_serialize_print_job(job) for job in print_queue.list_jobs()]}

    @router.get("/{job_id}")
    def get_job(job_id: str) -> dict[str, object]:
        job = print_queue.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return _serialize_print_job(job)

    @router.get("/{job_id}/segments")
    def get_job_segments(job_id: str) -> dict[str, list[dict[str, object]]]:
        if print_queue.get_job(job_id) is None:
            raise HTTPException(status_code=404, detail="job not found")
        return {
            "segments": [
                {
                    "index": segment.index,
                    "startRow": segment.start_row,
                    "heightDots": segment.height_dots,
                    "rasterByteOffset": segment.raster_byte_offset,
                    "rasterByteLength": segment.raster_byte_length,
                    "payloadBytes": segment.payload_bytes,
                    "blackDotCount": segment.black_dot_count,
                    "blackCoverage": segment.black_coverage,
                    "cooldownAfterMs": segment.cooldown_after_ms,
                    "sha256": segment.sha256,
                }
                for segment in print_queue.get_segments(job_id)
            ]
        }

    return router


def _find_profile(profiles: list[dict[str, Any]], profile_id: str) -> dict[str, Any]:
    for profile in profiles:
        if profile.get("id") == profile_id:
            return profile
    raise HTTPException(status_code=404, detail=f"unknown profile: {profile_id}")


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
                "blackDotCount": band.black_dot_count,
                "blackCoverage": band.black_coverage,
                "cooldownAfterMs": band.cooldown_after_ms,
                "sha256": band.sha256,
            }
            for band in package.bands
        ],
    }


def _serialize_print_job(job: PrintJob) -> dict[str, object]:
    return {
        "jobId": job.job_id,
        "previewId": job.preview_id,
        "planId": job.plan_id,
        "state": job.state,
        "phase": job.phase,
        "completionLevel": job.completion_level,
        "completionConfidence": job.completion_confidence,
        "requiresUserCheck": job.requires_user_check,
        "source": job.source,
        "copies": job.copies,
        "bandsSent": job.bands_sent,
        "totalBands": job.total_bands,
        "rowsSent": job.rows_sent,
        "totalRows": job.total_rows,
        "bytesSent": job.bytes_sent,
        "totalBytes": job.total_bytes,
        "tailBlankRowsDots": job.tail_blank_rows_dots,
        "safeActions": job.safe_actions,
    }
