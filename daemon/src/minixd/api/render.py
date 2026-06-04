from __future__ import annotations

import base64
import binascii
from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from minixd.render.preview_store import PreviewRecord, PreviewStore


class RenderPreviewRequest(BaseModel):
    document_hash: Annotated[str, Field(alias="documentHash", min_length=1)]
    render_settings_hash: Annotated[str, Field(alias="renderSettingsHash", min_length=1)]
    profile_id: Annotated[str, Field(alias="profileId", min_length=1)]
    width_dots: Annotated[int, Field(alias="widthDots", gt=0)]
    height_dots: Annotated[int, Field(alias="heightDots", gt=0)]
    raster_base64: Annotated[str, Field(alias="rasterBase64", min_length=1)]
    safety: dict[str, object]


def create_render_router(*, preview_store: PreviewStore) -> APIRouter:
    router = APIRouter(prefix="/v1/render", tags=["render"])

    @router.post("/preview")
    def render_preview(request: RenderPreviewRequest) -> dict[str, object]:
        raster = _decode_base64(request.raster_base64)
        record = preview_store.create(
            document_hash=request.document_hash,
            render_settings_hash=request.render_settings_hash,
            raster=raster,
            profile_id=request.profile_id,
            width_dots=request.width_dots,
            height_dots=request.height_dots,
            safety=request.safety,
        )
        return _serialize_preview_record(record, include_approval_token=True)

    @router.get("/previews/{preview_id}")
    def get_preview(preview_id: str) -> dict[str, object]:
        record = preview_store.get(preview_id)
        if record is None:
            raise HTTPException(status_code=404, detail="preview not found")
        return _serialize_preview_record(record, include_approval_token=False)

    return router


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
