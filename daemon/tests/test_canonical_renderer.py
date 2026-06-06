import base64
import json
from io import BytesIO
from pathlib import Path

from PIL import Image

from minixd.render.canonical import render_document

PROFILE_PATH = Path("profiles/seznik-minix-s1-lyin48d-gy/profile.json")


def test_rect_document_renders_exact_msb_packed_raster() -> None:
    document = {
        "schemaVersion": 1,
        "id": "doc_rect",
        "title": "Rect fixture",
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

    result = render_document(document)

    expected_row = bytes([0xFF]) + (b"\x00" * 47)
    assert result.width_dots == 384
    assert result.height_dots == 16
    assert result.row_bytes == 48
    assert result.packed_raster == (expected_row * 8) + (b"\x00" * 48 * 8)
    assert result.raster_hash.startswith("sha256:")
    assert result.preview_png.startswith(b"\x89PNG")
    assert result.safety["allowed"] is True
    assert result.safety["metrics"]["totalBlackCoverage"] == 64 / (384 * 16)


def test_text_document_renders_deterministically_without_system_fonts() -> None:
    document = {
        "schemaVersion": 1,
        "id": "doc_text",
        "title": "Text fixture",
        "target": {
            "profileId": "seznik-minix-s1-lyin48d-gy",
            "widthDots": 384,
            "heightDots": 80,
            "dpi": 203,
            "paperMode": "continuous",
            "density": "medium",
        },
        "background": {"color": "#ffffff"},
        "elements": [
            {
                "id": "text_1",
                "type": "text",
                "name": "Title",
                "x": 16,
                "y": 12,
                "width": 200,
                "height": 32,
                "rotation": 0,
                "locked": False,
                "visible": True,
                "text": "MINIX",
                "style": {"fill": "#000000"},
            }
        ],
        "assets": [],
        "metadata": {},
    }

    first = render_document(document)
    second = render_document(document)

    assert first.raster_hash == second.raster_hash
    assert first.safety["metrics"]["totalBlackPixels"] > 0


def test_qr_document_renders_deterministically_from_payload() -> None:
    document = {
        "schemaVersion": 1,
        "id": "doc_qr",
        "title": "QR fixture",
        "target": {
            "profileId": "seznik-minix-s1-lyin48d-gy",
            "widthDots": 384,
            "heightDots": 180,
            "dpi": 203,
            "paperMode": "continuous",
            "density": "medium",
        },
        "background": {"color": "#ffffff"},
        "elements": [
            {
                "id": "qr_1",
                "type": "qr",
                "name": "Setup QR",
                "x": 128,
                "y": 24,
                "width": 128,
                "height": 128,
                "rotation": 0,
                "locked": False,
                "visible": True,
                "payload": "https://minix.local/setup",
                "errorCorrectionLevel": "M",
            }
        ],
        "assets": [],
        "metadata": {},
    }
    changed_payload = {
        **document,
        "elements": [
            {
                **document["elements"][0],
                "payload": "https://minix.local/diagnostics",
            }
        ],
    }

    first = render_document(document)
    second = render_document(document)
    changed = render_document(changed_payload)

    assert first.raster_hash == second.raster_hash
    assert first.raster_hash != changed.raster_hash
    assert first.safety["metrics"]["totalBlackPixels"] > 0
    assert first.preview_png.startswith(b"\x89PNG")


def test_embedded_image_document_renders_thresholded_data_url() -> None:
    document = {
        "schemaVersion": 1,
        "id": "doc_image",
        "title": "Image fixture",
        "target": {
            "profileId": "seznik-minix-s1-lyin48d-gy",
            "widthDots": 384,
            "heightDots": 96,
            "dpi": 203,
            "paperMode": "continuous",
            "density": "medium",
        },
        "background": {"color": "#ffffff"},
        "elements": [
            {
                "id": "image_1",
                "type": "image",
                "name": "Logo",
                "x": 16,
                "y": 16,
                "width": 64,
                "height": 48,
                "rotation": 0,
                "locked": False,
                "visible": True,
                "fit": "contain",
                "source": {
                    "kind": "embedded_data_url",
                    "mimeType": "image/png",
                    "dataUrl": _png_data_url(),
                },
                "processing": {
                    "threshold": 128,
                    "invert": False,
                },
            }
        ],
        "assets": [],
        "metadata": {},
    }
    inverted = {
        **document,
        "elements": [
            {
                **document["elements"][0],
                "processing": {
                    "threshold": 128,
                    "invert": True,
                },
            }
        ],
    }

    first = render_document(document)
    second = render_document(document)
    changed = render_document(inverted)

    assert first.raster_hash == second.raster_hash
    assert first.raster_hash != changed.raster_hash
    assert first.safety["metrics"]["totalBlackPixels"] > 0
    assert first.preview_png.startswith(b"\x89PNG")


def test_profile_safety_blocks_dense_thermal_bands() -> None:
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    document = {
        "schemaVersion": 1,
        "id": "doc_dense",
        "title": "Dense blocked fixture",
        "target": {
            "profileId": "seznik-minix-s1-lyin48d-gy",
            "widthDots": 384,
            "heightDots": 64,
            "dpi": 203,
            "paperMode": "continuous",
            "density": "medium",
        },
        "background": {"color": "#ffffff"},
        "elements": [
            {
                "id": "rect_dense",
                "type": "rect",
                "name": "Solid thermal block",
                "x": 0,
                "y": 0,
                "width": 384,
                "height": 64,
                "rotation": 0,
                "locked": False,
                "visible": True,
                "fill": "#000000",
            }
        ],
        "assets": [],
        "metadata": {},
    }

    result = render_document(document, profile=profile)

    assert result.safety["allowed"] is False
    assert result.safety["metrics"]["totalBlackCoverage"] == 1.0
    assert result.safety["metrics"]["maxBandCoverage64"] == 1.0
    assert result.safety["warnings"] == [
        {
            "code": "total_black_coverage_high",
            "message": "Total black coverage is 100%, above the 35% warning limit.",
            "threshold": 0.35,
            "value": 1.0,
        }
    ]
    assert result.safety["errors"] == [
        {
            "code": "band_coverage_blocked",
            "message": "A 64-dot band is 100% black, above the 70% thermal safety limit.",
            "threshold": 0.7,
            "value": 1.0,
        }
    ]


def _png_data_url() -> str:
    image = Image.new("L", (2, 2), color=255)
    image.putpixel((0, 0), 0)
    image.putpixel((1, 1), 0)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
