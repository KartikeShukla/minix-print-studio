import base64

from fastapi.testclient import TestClient

from minixd.app import create_app


def test_render_preview_endpoint_stores_binding_metadata_without_raw_raster() -> None:
    client = TestClient(create_app(mock=True))

    response = client.post(
        "/v1/render/preview",
        json={
            "documentHash": "sha256:document",
            "renderSettingsHash": "sha256:settings",
            "profileId": "seznik-minix-s1-lyin48d-gy",
            "widthDots": 384,
            "heightDots": 2,
            "rasterBase64": base64.b64encode(b"\x00" * 96).decode("ascii"),
            "safety": {"allowed": True, "warnings": [], "metrics": {}},
        },
    )

    assert response.status_code == 200
    created = response.json()
    assert created["previewId"].startswith("prev_")
    assert created["approvalToken"].startswith("appr_")
    assert created["rasterHash"].startswith("sha256:")
    assert created["expiresAt"]

    get_response = client.get(f"/v1/render/previews/{created['previewId']}")

    assert get_response.status_code == 200
    stored = get_response.json()
    assert stored["previewId"] == created["previewId"]
    assert stored["documentHash"] == "sha256:document"
    assert stored["rasterHash"] == created["rasterHash"]
    assert "raster" not in stored


def test_render_preview_endpoint_recomputes_profile_safety_for_raw_raster() -> None:
    client = TestClient(create_app(mock=True))

    response = client.post(
        "/v1/render/preview",
        json={
            "documentHash": "sha256:dense-document",
            "renderSettingsHash": "sha256:settings",
            "profileId": "seznik-minix-s1-lyin48d-gy",
            "widthDots": 384,
            "heightDots": 64,
            "rasterBase64": base64.b64encode(b"\xFF" * 48 * 64).decode("ascii"),
            "safety": {"allowed": True, "warnings": [], "metrics": {}},
        },
    )

    assert response.status_code == 200
    safety = response.json()["safety"]
    assert safety["allowed"] is False
    assert safety["metrics"]["totalBlackCoverage"] == 1.0
    assert safety["metrics"]["maxBandCoverage64"] == 1.0
    assert safety["errors"][0]["code"] == "band_coverage_blocked"
