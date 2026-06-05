from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = ROOT / "apps" / "desktop" / "build"
SVG_PATH = BUILD_DIR / "icon-source.svg"
PNG_PATH = BUILD_DIR / "icon.png"
ICO_PATH = BUILD_DIR / "icon.ico"
ICONSET_DIR = BUILD_DIR / "icon.iconset"
ICON_SIZES = (16, 32, 64, 128, 256, 512, 1024)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate MiniX Print Studio desktop package icons."
    )
    parser.add_argument("--check", action="store_true", help="Validate generated icon files.")
    args = parser.parse_args()

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    if ICONSET_DIR.exists():
        shutil.rmtree(ICONSET_DIR)
    SVG_PATH.write_text(_source_svg(), encoding="utf-8")

    base = _draw_icon(1024)
    base.save(PNG_PATH)
    base.save(ICO_PATH, sizes=[(size, size) for size in ICON_SIZES if size <= 256])

    if args.check:
        _validate_outputs()
    return 0


def _validate_outputs() -> None:
    with Image.open(PNG_PATH) as png:
        if png.size != (1024, 1024):
            raise ValueError("icon.png must be 1024x1024")
    with Image.open(ICO_PATH) as ico:
        if (256, 256) not in getattr(ico, "ico").sizes():
            raise ValueError("icon.ico must include a 256x256 image")


def _draw_icon(size: int) -> Image.Image:
    scale = size / 1024
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    def xy(points: tuple[float, ...]) -> tuple[int, ...]:
        return tuple(round(point * scale) for point in points)

    draw.rounded_rectangle(
        xy((64, 64, 960, 960)),
        radius=round(212 * scale),
        fill=(23, 31, 42, 255),
    )
    draw.rounded_rectangle(
        xy((188, 220, 836, 626)),
        radius=round(82 * scale),
        fill=(244, 247, 251, 255),
    )
    draw.rounded_rectangle(
        xy((260, 316, 764, 486)),
        radius=round(42 * scale),
        fill=(42, 55, 70, 255),
    )
    draw.rectangle(xy((260, 432, 764, 486)), fill=(58, 72, 89, 255))
    draw.rounded_rectangle(
        xy((290, 526, 734, 838)),
        radius=round(34 * scale),
        fill=(255, 255, 255, 255),
    )
    draw.rounded_rectangle(
        xy((338, 578, 686, 618)),
        radius=round(20 * scale),
        fill=(36, 112, 105, 255),
    )
    draw.rounded_rectangle(
        xy((338, 660, 620, 698)),
        radius=round(19 * scale),
        fill=(36, 112, 105, 255),
    )
    draw.rounded_rectangle(
        xy((338, 740, 702, 778)),
        radius=round(19 * scale),
        fill=(36, 112, 105, 255),
    )
    draw.ellipse(xy((682, 268, 758, 344)), fill=(234, 85, 69, 255))
    draw.rounded_rectangle(
        xy((236, 188, 788, 276)),
        radius=round(44 * scale),
        fill=(36, 112, 105, 255),
    )
    return image


def _source_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" role="img">
  <title>MiniX Print Studio icon</title>
  <rect x="64" y="64" width="896" height="896" rx="212" fill="#171f2a"/>
  <rect x="188" y="220" width="648" height="406" rx="82" fill="#f4f7fb"/>
  <rect x="260" y="316" width="504" height="170" rx="42" fill="#2a3746"/>
  <path d="M260 432h504v54H260z" fill="#3a4859"/>
  <rect x="290" y="526" width="444" height="312" rx="34" fill="#fff"/>
  <rect x="338" y="578" width="348" height="40" rx="20" fill="#247069"/>
  <rect x="338" y="660" width="282" height="38" rx="19" fill="#247069"/>
  <rect x="338" y="740" width="364" height="38" rx="19" fill="#247069"/>
  <circle cx="720" cy="306" r="38" fill="#ea5545"/>
  <rect x="236" y="188" width="552" height="88" rx="44" fill="#247069"/>
</svg>
"""


if __name__ == "__main__":
    raise SystemExit(main())
