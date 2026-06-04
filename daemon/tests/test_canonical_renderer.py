from minixd.render.canonical import render_document


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
