from __future__ import annotations

import hashlib
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from minixd.raster.packing import calculate_black_coverage, pack_rows_msb


@dataclass(frozen=True)
class RenderedDocument:
    width_dots: int
    height_dots: int
    row_bytes: int
    packed_raster: bytes
    raster_hash: str
    preview_png: bytes
    safety: dict[str, object]


def render_document(document: dict[str, Any]) -> RenderedDocument:
    target = _dict_value(document, "target")
    width_dots = _int_value(target, "widthDots")
    height_dots = _int_value(target, "heightDots")
    if width_dots % 8 != 0:
        raise ValueError("document target widthDots must be divisible by 8")

    image = Image.new("L", (width_dots, height_dots), color=255)
    draw = ImageDraw.Draw(image)

    for element in _list_value(document, "elements"):
        if not isinstance(element, dict):
            raise ValueError("document elements must be objects")
        if element.get("visible") is False:
            continue
        element_type = element.get("type")
        if element_type == "rect":
            _draw_rect(draw, element)
        elif element_type == "text":
            _draw_text(draw, element)

    packed = _pack_thresholded_image(image)
    preview = _png_bytes(image)
    return RenderedDocument(
        width_dots=width_dots,
        height_dots=height_dots,
        row_bytes=width_dots // 8,
        packed_raster=packed,
        raster_hash=_sha256(packed),
        preview_png=preview,
        safety=_build_safety_report(packed, width_dots=width_dots, height_dots=height_dots),
    )


def render_settings_hash(render_settings: dict[str, object]) -> str:
    canonical = repr(sorted(render_settings.items())).encode("utf-8")
    return _sha256(canonical)


def document_hash(document: dict[str, Any]) -> str:
    canonical = repr(_stable(document)).encode("utf-8")
    return _sha256(canonical)


def _draw_rect(draw: ImageDraw.ImageDraw, element: dict[str, Any]) -> None:
    x = _intish(element, "x")
    y = _intish(element, "y")
    width = _intish(element, "width")
    height = _intish(element, "height")
    if width <= 0 or height <= 0:
        return

    fill = 0 if _color_value(element.get("fill", "#000000")) < 128 else 255
    draw.rectangle((x, y, x + width - 1, y + height - 1), fill=fill)


def _draw_text(draw: ImageDraw.ImageDraw, element: dict[str, Any]) -> None:
    text = str(element.get("text", ""))
    if not text:
        return
    style = element.get("style", {})
    fill_source = style.get("fill", "#000000") if isinstance(style, dict) else "#000000"
    fill = 0 if _color_value(fill_source) < 128 else 255
    font = ImageFont.load_default()
    draw.text((_intish(element, "x"), _intish(element, "y")), text, fill=fill, font=font)


def _pack_thresholded_image(image: Image.Image) -> bytes:
    width, height = image.size
    rows: list[list[int]] = []
    pixels = image.tobytes()
    for y in range(height):
        row_start = y * width
        row: list[int] = []
        for x in range(width):
            row.append(1 if pixels[row_start + x] < 128 else 0)
        rows.append(row)
    return pack_rows_msb(rows, width_dots=width)


def _png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _build_safety_report(
    packed: bytes,
    *,
    width_dots: int,
    height_dots: int,
) -> dict[str, object]:
    total_black_pixels = sum(value.bit_count() for value in packed)
    total_pixels = width_dots * height_dots
    coverage = calculate_black_coverage(packed, width_dots=width_dots, height_dots=height_dots)
    return {
        "allowed": True,
        "warnings": [],
        "errors": [],
        "metrics": {
            "heightDots": height_dots,
            "totalBlackPixels": total_black_pixels,
            "totalPixels": total_pixels,
            "totalBlackCoverage": coverage,
            "maxBandCoverage64": coverage,
        },
    }


def _color_value(value: object) -> int:
    if not isinstance(value, str):
        return 0
    if value.startswith("#") and len(value) == 7:
        red = int(value[1:3], 16)
        green = int(value[3:5], 16)
        blue = int(value[5:7], 16)
        return round((red + green + blue) / 3)
    return 0


def _stable(value: object) -> object:
    if isinstance(value, dict):
        return {key: _stable(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_stable(item) for item in value]
    return value


def _sha256(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _dict_value(source: dict[str, Any], key: str) -> dict[str, Any]:
    value = source[key]
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def _list_value(source: dict[str, Any], key: str) -> list[object]:
    value = source[key]
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list")
    return value


def _int_value(source: dict[str, Any], key: str) -> int:
    value = source[key]
    if not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return value


def _intish(source: dict[str, Any], key: str) -> int:
    value = source[key]
    if not isinstance(value, int | float):
        raise ValueError(f"{key} must be numeric")
    return int(round(value))
