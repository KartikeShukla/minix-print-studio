from datetime import UTC, datetime, timedelta

import pytest

from minixd.render.preview_store import (
    PreviewBindingError,
    PreviewStore,
    create_preview_record,
)


def test_preview_record_hashes_raster_and_requires_matching_document_settings_and_token() -> None:
    now = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)
    record = create_preview_record(
        preview_id="prev_1",
        approval_token="appr_1",
        document_hash="sha256:document",
        render_settings_hash="sha256:settings",
        raster=b"\xAA\x55",
        profile_id="seznik-minix-s1-lyin48d-gy",
        width_dots=384,
        height_dots=1,
        safety={"allowed": True, "warnings": [], "metrics": {}},
        created_at=now,
        expires_at=now + timedelta(minutes=10),
    )

    assert record.raster_hash.startswith("sha256:")
    assert record.verify_binding(
        approval_token="appr_1",
        document_hash="sha256:document",
        render_settings_hash="sha256:settings",
        now=now,
    )

    with pytest.raises(PreviewBindingError, match="document changed"):
        record.verify_binding(
            approval_token="appr_1",
            document_hash="sha256:other",
            render_settings_hash="sha256:settings",
            now=now,
        )

    with pytest.raises(PreviewBindingError, match="approval token"):
        record.verify_binding(
            approval_token="wrong",
            document_hash="sha256:document",
            render_settings_hash="sha256:settings",
            now=now,
        )


def test_preview_store_rejects_expired_previews() -> None:
    now = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)
    store = PreviewStore(now=lambda: now)
    record = store.create(
        document_hash="sha256:document",
        render_settings_hash="sha256:settings",
        raster=b"\x00",
        profile_id="seznik-minix-s1-lyin48d-gy",
        width_dots=384,
        height_dots=1,
        safety={"allowed": True, "warnings": [], "metrics": {}},
        ttl=timedelta(seconds=1),
    )

    expired_store = PreviewStore(now=lambda: now + timedelta(seconds=2))
    expired_store.put(record)

    with pytest.raises(PreviewBindingError, match="expired"):
        expired_store.verify(
            preview_id=record.preview_id,
            approval_token=record.approval_token,
            document_hash=record.document_hash,
            render_settings_hash=record.render_settings_hash,
        )
