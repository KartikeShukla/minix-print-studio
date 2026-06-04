import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient

from minixd.app import create_app


def test_print_endpoint_queues_mock_job_and_exposes_status_and_segments() -> None:
    client = TestClient(create_app(mock=True))
    document = {
        "schemaVersion": 1,
        "id": "doc_print",
        "title": "Print API fixture",
        "target": {
            "profileId": "seznik-minix-s1-lyin48d-gy",
            "widthDots": 384,
            "heightDots": 16,
            "dpi": 203,
            "paperMode": "continuous",
            "density": "medium",
        },
        "background": {"color": "#ffffff"},
        "elements": [
            {
                "id": "rect_1",
                "type": "rect",
                "name": "Black mark",
                "x": 0,
                "y": 0,
                "width": 8,
                "height": 8,
                "rotation": 0,
                "locked": False,
                "visible": True,
                "fill": "#000000",
            }
        ],
        "assets": [],
        "metadata": {},
    }
    preview_response = client.post(
        "/v1/render/document-preview",
        json={"document": document, "renderSettings": {"threshold": 128, "dither": "none"}},
    )
    preview = preview_response.json()

    print_response = client.post(
        "/v1/jobs/print",
        json={
            "previewId": preview["previewId"],
            "approvalToken": preview["approvalToken"],
            "documentHash": preview["documentHash"],
            "renderSettingsHash": preview["renderSettingsHash"],
            "profileId": "seznik-minix-s1-lyin48d-gy",
            "paperMode": "continuous",
            "density": "medium",
            "copies": 1,
            "source": "ui",
        },
    )

    assert print_response.status_code == 200
    job = print_response.json()
    assert job["state"] == "completed_unverified"
    assert job["completionLevel"] == "unverified"
    assert job["requiresUserCheck"] is True
    assert job["bandsSent"] == job["totalBands"]
    assert job["rowsSent"] == 176
    assert job["tailBlankRowsDots"] == 160
    assert job["safeActions"] == ["confirm_complete", "feed_paper", "reprint_from_start"]

    get_response = client.get(f"/v1/jobs/{job['jobId']}")
    assert get_response.status_code == 200
    assert get_response.json()["jobId"] == job["jobId"]

    list_response = client.get("/v1/jobs")
    assert list_response.status_code == 200
    assert list_response.json()["jobs"][0]["jobId"] == job["jobId"]

    segments_response = client.get(f"/v1/jobs/{job['jobId']}/segments")
    assert segments_response.status_code == 200
    assert segments_response.json()["segments"][0]["rasterByteLength"] == 8_448
    assert "raster" not in segments_response.json()["segments"][0]


def test_print_endpoint_rejects_bad_approval_token_without_creating_job() -> None:
    client = TestClient(create_app(mock=True))
    document = {
        "schemaVersion": 1,
        "id": "doc_bad_token",
        "title": "Bad token",
        "target": {
            "profileId": "seznik-minix-s1-lyin48d-gy",
            "widthDots": 384,
            "heightDots": 16,
            "dpi": 203,
            "paperMode": "continuous",
            "density": "medium",
        },
        "background": {"color": "#ffffff"},
        "elements": [],
        "assets": [],
        "metadata": {},
    }
    preview = client.post(
        "/v1/render/document-preview",
        json={"document": document, "renderSettings": {}},
    ).json()

    response = client.post(
        "/v1/jobs/print",
        json={
            "previewId": preview["previewId"],
            "approvalToken": "wrong",
            "documentHash": preview["documentHash"],
            "renderSettingsHash": preview["renderSettingsHash"],
            "profileId": "seznik-minix-s1-lyin48d-gy",
            "paperMode": "continuous",
            "density": "medium",
            "copies": 1,
            "source": "ui",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "approval token mismatch"
    assert client.get("/v1/jobs").json() == {"jobs": []}


def test_print_jobs_survive_daemon_app_restart_with_data_dir(tmp_path: Path) -> None:
    client = TestClient(create_app(mock=True, data_dir=tmp_path))
    document = {
        "schemaVersion": 1,
        "id": "doc_persisted_job",
        "title": "Persisted job",
        "target": {
            "profileId": "seznik-minix-s1-lyin48d-gy",
            "widthDots": 384,
            "heightDots": 16,
            "dpi": 203,
            "paperMode": "continuous",
            "density": "medium",
        },
        "background": {"color": "#ffffff"},
        "elements": [],
        "assets": [],
        "metadata": {},
    }
    preview = client.post(
        "/v1/render/document-preview",
        json={"document": document, "renderSettings": {}},
    ).json()
    printed = client.post(
        "/v1/jobs/print",
        json={
            "previewId": preview["previewId"],
            "approvalToken": preview["approvalToken"],
            "documentHash": preview["documentHash"],
            "renderSettingsHash": preview["renderSettingsHash"],
            "profileId": "seznik-minix-s1-lyin48d-gy",
            "paperMode": "continuous",
            "density": "medium",
            "copies": 1,
            "source": "ui",
        },
    ).json()

    restarted = TestClient(create_app(mock=True, data_dir=tmp_path))

    listed = restarted.get("/v1/jobs").json()["jobs"]
    assert listed[0]["jobId"] == printed["jobId"]
    assert listed[0]["completionLevel"] == "unverified"
    segments = restarted.get(f"/v1/jobs/{printed['jobId']}/segments").json()["segments"]
    assert segments[0]["rasterByteLength"] == 8_448
    diagnostics = restarted.post("/v1/diagnostics/export", json={}).json()
    assert diagnostics["jobs"][0]["jobId"] == printed["jobId"]


def test_diagnostics_export_includes_redacted_job_and_segment_metadata() -> None:
    client = TestClient(create_app(mock=True))
    document = {
        "schemaVersion": 1,
        "id": "doc_diagnostics",
        "title": "Diagnostics fixture /Users/alice/private-image.png",
        "target": {
            "profileId": "seznik-minix-s1-lyin48d-gy",
            "widthDots": 384,
            "heightDots": 16,
            "dpi": 203,
            "paperMode": "continuous",
            "density": "medium",
        },
        "background": {"color": "#ffffff"},
        "elements": [],
        "assets": [],
        "metadata": {},
    }
    preview = client.post(
        "/v1/render/document-preview",
        json={"document": document, "renderSettings": {"token": "super-secret-token"}},
    ).json()
    printed = client.post(
        "/v1/jobs/print",
        json={
            "previewId": preview["previewId"],
            "approvalToken": preview["approvalToken"],
            "documentHash": preview["documentHash"],
            "renderSettingsHash": preview["renderSettingsHash"],
            "profileId": "seznik-minix-s1-lyin48d-gy",
            "paperMode": "continuous",
            "density": "medium",
            "copies": 1,
            "source": "ui",
        },
    ).json()

    response = client.post("/v1/diagnostics/export", json={"includeProjectContent": False})

    assert response.status_code == 200
    bundle = response.json()
    assert bundle["schemaVersion"] == 1
    assert bundle["redaction"]["projectContentIncluded"] is False
    assert bundle["daemon"]["mock"] is True
    assert bundle["profiles"][0]["id"] == "seznik-minix-s1-lyin48d-gy"
    assert bundle["jobs"][0]["jobId"] == printed["jobId"]
    assert bundle["jobs"][0]["completionDecision"]["level"] == "unverified"
    assert bundle["jobs"][0]["completionDecision"]["requiresUserCheck"] is True
    assert bundle["jobs"][0]["segments"][0]["rasterByteLength"] == 8_448
    assert "raster" not in bundle["jobs"][0]["segments"][0]
    assert "approvalToken" not in str(bundle)
    assert "super-secret-token" not in str(bundle)
    assert "/Users/alice" not in str(bundle)

    archive_response = client.post(
        "/v1/diagnostics/export/archive",
        json={"includeProjectContent": False},
    )

    assert archive_response.status_code == 200
    assert archive_response.headers["content-type"] == "application/zip"
    with ZipFile(BytesIO(archive_response.content)) as archive:
        names = archive.namelist()
        assert names == ["diagnostics.json", "README.md"]
        archived_bundle = json.loads(archive.read("diagnostics.json"))
        assert archived_bundle["jobs"][0]["jobId"] == printed["jobId"]
        assert "approvalToken" not in archive.read("diagnostics.json").decode("utf-8")
