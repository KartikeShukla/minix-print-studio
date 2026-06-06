import json
from pathlib import Path

import pytest

from minixd.printing.queue import PrintQueue, PrintRejectedError
from minixd.printing.transport import PrintTransportResult
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


def test_mock_print_queue_reports_partial_output_after_segment_boundary_disconnect() -> None:
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
    queue = PrintQueue(
        profiles=[profile],
        preview_store=preview_store,
        mock=True,
        mock_disconnect_after_band_index=0,
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

    assert job.state == "failed_partial_output"
    assert job.phase == "transport_disconnected"
    assert job.completion_level == "failed_partial_output"
    assert job.completion_confidence == "mock_disconnect_after_band_0"
    assert job.requires_user_check is True
    assert job.bands_sent == 1
    assert job.total_bands == 2
    assert job.rows_sent == 256
    assert job.total_rows == 460
    assert job.bytes_sent == 12_288
    assert job.total_bytes == 22_080
    assert job.safe_actions == ["inspect_output", "clear_printer", "reprint_from_start"]


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


def test_physical_print_queue_requires_explicit_device_id() -> None:
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
    queue = PrintQueue(
        profiles=[profile],
        preview_store=preview_store,
        mock=False,
        transport=FakePrintTransport(),
    )

    with pytest.raises(PrintRejectedError, match="deviceId is required"):
        queue.print_preview(
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


def test_physical_print_queue_uses_transport_and_reports_unverified_completion() -> None:
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
    transport = FakePrintTransport()
    queue = PrintQueue(
        profiles=[profile],
        preview_store=preview_store,
        mock=False,
        transport=transport,
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
        device_id="dev_minix",
    )

    assert transport.calls == [
        {
            "device_id": "dev_minix",
            "profile_id": "seznik-minix-s1-lyin48d-gy",
            "total_bands": 1,
        }
    ]
    assert job.device_id == "dev_minix"
    assert job.state == "completed_unverified"
    assert job.phase == "waiting_for_user_confirmation"
    assert job.completion_confidence == "ble_transfer_completed_final_ack_unverified"
    assert job.bands_sent == 1
    assert job.rows_sent == 161
    assert job.bytes_sent == 7_728
    assert job.safe_actions == ["confirm_complete", "feed_paper", "reprint_from_start"]


class FakePrintTransport:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def print_plan(
        self,
        *,
        device_id: str,
        profile: dict[str, object],
        plan_package: object,
    ) -> PrintTransportResult:
        total_bands = len(plan_package.bands)
        self.calls.append(
            {
                "device_id": device_id,
                "profile_id": profile["id"],
                "total_bands": total_bands,
            }
        )
        return PrintTransportResult(
            bands_sent=total_bands,
            rows_sent=plan_package.plan.transfer_height_dots,
            raster_bytes_sent=plan_package.plan.total_raster_bytes,
            protocol_bytes_sent=plan_package.plan.total_raster_bytes + 32,
            notification_count=0,
        )
