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
