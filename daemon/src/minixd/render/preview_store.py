from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4


class PreviewBindingError(ValueError):
    """Raised when a stored preview can no longer authorize printing."""


@dataclass(frozen=True)
class PreviewRecord:
    preview_id: str
    approval_token: str
    document_hash: str
    render_settings_hash: str
    raster_hash: str
    raster: bytes
    profile_id: str
    width_dots: int
    height_dots: int
    safety: dict[str, object]
    created_at: datetime
    expires_at: datetime

    def verify_binding(
        self,
        *,
        approval_token: str,
        document_hash: str,
        render_settings_hash: str,
        now: datetime,
    ) -> bool:
        if now >= self.expires_at:
            raise PreviewBindingError("preview expired")
        if approval_token != self.approval_token:
            raise PreviewBindingError("approval token mismatch")
        if document_hash != self.document_hash:
            raise PreviewBindingError("document changed after preview")
        if render_settings_hash != self.render_settings_hash:
            raise PreviewBindingError("render settings changed after preview")
        return True


class PreviewStore:
    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        self._now = now or (lambda: datetime.now(tz=UTC))
        self._records: dict[str, PreviewRecord] = {}

    def create(
        self,
        *,
        document_hash: str,
        render_settings_hash: str,
        raster: bytes,
        profile_id: str,
        width_dots: int,
        height_dots: int,
        safety: dict[str, object],
        ttl: timedelta = timedelta(minutes=10),
    ) -> PreviewRecord:
        now = self._now()
        record = create_preview_record(
            preview_id=f"prev_{uuid4().hex}",
            approval_token=f"appr_{uuid4().hex}",
            document_hash=document_hash,
            render_settings_hash=render_settings_hash,
            raster=raster,
            profile_id=profile_id,
            width_dots=width_dots,
            height_dots=height_dots,
            safety=safety,
            created_at=now,
            expires_at=now + ttl,
        )
        self.put(record)
        return record

    def put(self, record: PreviewRecord) -> None:
        self._records[record.preview_id] = record

    def get(self, preview_id: str) -> PreviewRecord | None:
        return self._records.get(preview_id)

    def verify(
        self,
        *,
        preview_id: str,
        approval_token: str,
        document_hash: str,
        render_settings_hash: str,
    ) -> PreviewRecord:
        record = self.get(preview_id)
        if record is None:
            raise PreviewBindingError("preview not found")
        record.verify_binding(
            approval_token=approval_token,
            document_hash=document_hash,
            render_settings_hash=render_settings_hash,
            now=self._now(),
        )
        return record


def create_preview_record(
    *,
    preview_id: str,
    approval_token: str,
    document_hash: str,
    render_settings_hash: str,
    raster: bytes,
    profile_id: str,
    width_dots: int,
    height_dots: int,
    safety: dict[str, object],
    created_at: datetime,
    expires_at: datetime,
) -> PreviewRecord:
    if width_dots <= 0 or height_dots <= 0:
        raise ValueError("preview dimensions must be positive")
    if not preview_id:
        raise ValueError("preview_id is required")
    if not approval_token:
        raise ValueError("approval_token is required")

    return PreviewRecord(
        preview_id=preview_id,
        approval_token=approval_token,
        document_hash=document_hash,
        render_settings_hash=render_settings_hash,
        raster_hash=_sha256(raster),
        raster=raster,
        profile_id=profile_id,
        width_dots=width_dots,
        height_dots=height_dots,
        safety=safety,
        created_at=created_at,
        expires_at=expires_at,
    )


def _sha256(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"
