import json
from pathlib import Path

import pytest

from minixd.printing.queue import PrintQueue, PrintRejectedError
from minixd.render.preview_store import PreviewStore

PROFILE_PATH = Path("profiles/seznik-minix-s1-lyin48d-gy/profile.json")


def load_profile() -> dict[str, object]:
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def test_mock_print_queue_consumes_preview_and_reports_unverified_completion() -> None:
    preview_store = PreviewStore()
    profile = load_profile()
    raster = b"\x00" * 48 * 300
    preview = preview_store.create(
        document_hash="sha256:document",
        render_settings_hash="sha256:settings",
        raster=raster,
        profile_id="seznik-minix-s1-lyin48d-gy",
        width_dots=384,
        height_dots=300,
        safety={"allowed": True, "warnings": [], "metrics": {}},
    )
    queue = PrintQueue(profiles=[profile], preview_store=preview_store, mock=True)

    job = queue.print_preview(
        preview_id=preview.preview_id,
        approval_token=preview.approval_token,
        document_hash=preview.document_hash,
        render_settings_hash=preview.render_settings_hash,
        profile_id=preview.profile_id,
        paper_mode="continuous",
        density="medium",
        copies=1,
        source="ui",
    )

    assert job.job_id.startswith("job_")
    assert job.state == "completed_unverified"
    assert job.phase == "waiting_for_final_status"
    assert job.completion_level == "unverified"
    assert job.requires_user_check is True
    assert job.bands_sent == 2
    assert job.total_bands == 2
    assert job.rows_sent == 460
    assert job.total_rows == 460
    assert job.bytes_sent == 22_080
    assert job.total_bytes == 22_080
    assert job.tail_blank_rows_dots == 160
    assert job.safe_actions == ["confirm_complete", "feed_paper", "reprint_from_start"]
    assert queue.get_job(job.job_id) == job
    assert len(queue.get_segments(job.job_id)) == 2


def test_mock_print_queue_persists_job_and_redacted_segment_metadata(tmp_path: Path) -> None:
    preview_store = PreviewStore()
    profile = load_profile()
    raster = b"\x00" * 48 * 300
    preview = preview_store.create(
        document_hash="sha256:document",
        render_settings_hash="sha256:settings",
        raster=raster,
        profile_id="seznik-minix-s1-lyin48d-gy",
        width_dots=384,
        height_dots=300,
        safety={"allowed": True, "warnings": [], "metrics": {}},
    )
    store_path = tmp_path / "jobs.json"
    queue = PrintQueue(
        profiles=[profile],
        preview_store=preview_store,
        mock=True,
        job_store_path=store_path,
    )

    job = queue.print_preview(
        preview_id=preview.preview_id,
        approval_token=preview.approval_token,
        document_hash=preview.document_hash,
        render_settings_hash=preview.render_settings_hash,
        profile_id=preview.profile_id,
        paper_mode="continuous",
        density="medium",
        copies=1,
        source="ui",
    )

    restored = PrintQueue(
        profiles=[profile],
        preview_store=PreviewStore(),
        mock=True,
        job_store_path=store_path,
    )

    assert restored.get_job(job.job_id) == job
    restored_segment = restored.get_segments(job.job_id)[0]
    assert restored_segment.raster == b""
    assert restored_segment.raster_byte_length == 12_288
    stored = store_path.read_text(encoding="utf-8")
    assert "approvalToken" not in stored
    assert '"raster":' not in stored


def test_mock_print_queue_rejects_bad_approval_token_before_output() -> None:
    preview_store = PreviewStore()
    profile = load_profile()
    preview = preview_store.create(
        document_hash="sha256:document",
        render_settings_hash="sha256:settings",
        raster=b"\x00" * 48,
        profile_id="seznik-minix-s1-lyin48d-gy",
        width_dots=384,
        height_dots=1,
        safety={"allowed": True, "warnings": [], "metrics": {}},
    )
    queue = PrintQueue(profiles=[profile], preview_store=preview_store, mock=True)

    with pytest.raises(PrintRejectedError, match="approval token mismatch"):
        queue.print_preview(
            preview_id=preview.preview_id,
            approval_token="wrong",
            document_hash=preview.document_hash,
            render_settings_hash=preview.render_settings_hash,
            profile_id=preview.profile_id,
            paper_mode="continuous",
            density="medium",
            copies=1,
            source="ui",
        )
