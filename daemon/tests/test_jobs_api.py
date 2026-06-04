import base64

from fastapi.testclient import TestClient

from minixd.app import create_app


def test_plan_job_endpoint_returns_segment_metadata_without_raw_raster() -> None:
    client = TestClient(create_app(mock=True))
    row_bytes = 48
    content_height = 300
    content_raster = bytes([0x55]) * row_bytes * content_height

    response = client.post(
        "/v1/jobs/plan",
        json={
            "jobId": "job_api",
            "previewId": "prev_api",
            "documentHash": "sha256:document",
            "profileId": "seznik-minix-s1-lyin48d-gy",
            "paperMode": "continuous",
            "density": "medium",
            "contentHeightDots": content_height,
            "contentRasterBase64": base64.b64encode(content_raster).decode("ascii"),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["plan"]["planId"] == "plan_job_api"
    assert body["plan"]["transferHeightDots"] == 460
    assert body["plan"]["tailBlankRowsDots"] == 160
    assert body["totalBands"] == 2
    assert body["bands"][0]["heightDots"] == 256
    assert body["bands"][0]["rasterByteLength"] == 12288
    assert body["bands"][0]["payloadBytes"] == 12296
    assert "raster" not in body["bands"][0]
