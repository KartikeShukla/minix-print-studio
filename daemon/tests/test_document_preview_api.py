from fastapi.testclient import TestClient

from minixd.app import create_app
from minixd.render.canonical import render_document


def test_document_preview_endpoint_renders_and_stores_daemon_canonical_raster() -> None:
    client = TestClient(create_app(mock=True))
    document = {
        "schemaVersion": 1,
        "id": "doc_api",
        "title": "API fixture",
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
    expected = render_document(document)

    response = client.post(
        "/v1/render/document-preview",
        json={
            "document": document,
            "renderSettings": {"threshold": 128, "dither": "none"},
        },
    )

    assert response.status_code == 200
    created = response.json()
    assert created["previewId"].startswith("prev_")
    assert created["approvalToken"].startswith("appr_")
    assert created["rasterHash"] == expected.raster_hash
    assert created["widthDots"] == 384
    assert created["heightDots"] == 16
    assert created["safety"]["metrics"]["totalBlackPixels"] == 64
    assert "raster" not in created
