from __future__ import annotations

import base64
import binascii
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from minixd.render.canonical import (
    build_raster_safety_report,
    document_hash,
    render_document,
    render_settings_hash,
)
from minixd.render.preview_store import PreviewRecord, PreviewStore


class RenderPreviewRequest(BaseModel):
    document_hash: Annotated[str, Field(alias="documentHash", min_length=1)]
    render_settings_hash: Annotated[str, Field(alias="renderSettingsHash", min_length=1)]
    profile_id: Annotated[str, Field(alias="profileId", min_length=1)]
    width_dots: Annotated[int, Field(alias="widthDots", gt=0)]
    height_dots: Annotated[int, Field(alias="heightDots", gt=0)]
    raster_base64: Annotated[str, Field(alias="rasterBase64", min_length=1)]
    safety: dict[str, object]


class RenderDocumentPreviewRequest(BaseModel):
    document: dict[str, object]
    render_settings: Annotated[
        dict[str, object],
        Field(alias="renderSettings", default_factory=dict),
    ]


def create_render_router(
    *,
    preview_store: PreviewStore,
    profiles: list[dict[str, Any]],
) -> APIRouter:
    router = APIRouter(prefix="/v1/render", tags=["render"])

    @router.post("/preview")
    def render_preview(request: RenderPreviewRequest) -> dict[str, object]:
        raster = _decode_base64(request.raster_base64)
        profile = _find_profile(profiles, request.profile_id)
        safety = build_raster_safety_report(
            raster,
            width_dots=request.width_dots,
            height_dots=request.height_dots,
            profile=profile,
        )
        record = preview_store.create(
            document_hash=request.document_hash,
            render_settings_hash=request.render_settings_hash,
            raster=raster,
            profile_id=request.profile_id,
            width_dots=request.width_dots,
            height_dots=request.height_dots,
            safety=safety,
        )
        return _serialize_preview_record(record, include_approval_token=True)

    @router.post("/document-preview")
    def render_document_preview(request: RenderDocumentPreviewRequest) -> dict[str, object]:
        target = request.document.get("target")
        if not isinstance(target, dict):
            raise HTTPException(status_code=422, detail="document.target is required")
        profile_id = target.get("profileId")
        if not isinstance(profile_id, str):
            raise HTTPException(status_code=422, detail="document.target.profileId is required")
        profile = _find_profile(profiles, profile_id)
        rendered = render_document(request.document, profile=profile)
        record = preview_store.create(
            document_hash=document_hash(request.document),
            render_settings_hash=render_settings_hash(request.render_settings),
            raster=rendered.packed_raster,
            profile_id=profile_id,
            width_dots=rendered.width_dots,
            height_dots=rendered.height_dots,
            safety=rendered.safety,
        )
        return _serialize_preview_record(record, include_approval_token=True)

    @router.get("/previews/{preview_id}")
    def get_preview(preview_id: str) -> dict[str, object]:
        record = preview_store.get(preview_id)
        if record is None:
            raise HTTPException(status_code=404, detail="preview not found")
        return _serialize_preview_record(record, include_approval_token=False)

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
        raise HTTPException(status_code=400, detail="rasterBase64 is invalid") from exc


def _serialize_preview_record(
    record: PreviewRecord,
    *,
    include_approval_token: bool,
) -> dict[str, object]:
    response: dict[str, object] = {
        "previewId": record.preview_id,
        "documentHash": record.document_hash,
        "renderSettingsHash": record.render_settings_hash,
        "rasterHash": record.raster_hash,
        "profileId": record.profile_id,
        "widthDots": record.width_dots,
        "heightDots": record.height_dots,
        "safety": record.safety,
        "createdAt": record.created_at.isoformat(),
        "expiresAt": record.expires_at.isoformat(),
    }
    if include_approval_token:
        response["approvalToken"] = record.approval_token
    return response
