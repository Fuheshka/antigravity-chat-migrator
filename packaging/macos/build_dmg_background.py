#!/usr/bin/env python3
"""Generate Apple HIG-compliant Retina multi-resolution TIFF background for DMG."""

import os
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw, ImageFont


def draw_artwork(width: int, height: int, scale: int = 1) -> Image.Image:
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Sleek Modern Dark Mode Canvas (#18181c to #222228)
    for y in range(height):
        factor = y / height
        r = int(24 + (34 - 24) * factor)
        g = int(24 + (34 - 24) * factor)
        b = int(28 + (40 - 28) * factor)
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))

    # 2. Outer Glassmorphism Card Outline (Top/Sides: 16px, Bottom: 36px)
    margin_x = 16 * scale
    margin_top = 16 * scale
    margin_bottom = 36 * scale
    draw.rounded_rectangle(
        [margin_x, margin_top, width - margin_x, height - margin_bottom],
        radius=16 * scale,
        outline=(255, 255, 255, 35),
        width=1 * scale,
    )

    # Icon Centers (1x: Left=(160, 140), Right=(500, 140))
    left_x = 160 * scale
    right_x = 500 * scale

    # 3. High-Contrast White Label Cards
    # Left pill card: accommodates 2-line title ("Antigravity Chat \n Migrator.app")
    # Top at 206px, bottom at 260px (height = 54px), width = 176px
    label_left_w = 176 * scale
    label_left_top = 206 * scale
    label_left_bottom = 260 * scale

    # Right pill card: accommodates 1-line title ("Applications")
    # Top at 208px, bottom at 244px (height = 36px), width = 140px
    label_right_w = 140 * scale
    label_right_top = 208 * scale
    label_right_bottom = 244 * scale

    # Left pill card (App / Executable)
    draw.rounded_rectangle(
        [left_x - label_left_w / 2, label_left_top, left_x + label_left_w / 2, label_left_bottom],
        radius=8 * scale,
        fill=(255, 255, 255, 240),
        outline=(255, 255, 255, 255),
        width=1 * scale,
    )

    # Right pill card (Applications)
    draw.rounded_rectangle(
        [right_x - label_right_w / 2, label_right_top, right_x + label_right_w / 2, label_right_bottom],
        radius=8 * scale,
        fill=(255, 255, 255, 240),
        outline=(255, 255, 255, 255),
        width=1 * scale,
    )

    # 4. Center Arrow Indicator (between x=245 and x=415 at y=140)
    arrow_y = 140 * scale
    arrow_start_x = 245 * scale
    arrow_end_x = 415 * scale

    draw.line(
        [(arrow_start_x, arrow_y), (arrow_end_x, arrow_y)],
        fill=(255, 255, 255, 180),
        width=3 * scale,
    )
    draw.polygon(
        [
            (arrow_end_x - 14 * scale, arrow_y - 10 * scale),
            (arrow_end_x + 4 * scale, arrow_y),
            (arrow_end_x - 14 * scale, arrow_y + 10 * scale),
        ],
        fill=(255, 255, 255, 230),
    )

    # 5. Bottom Instructional Typography (y=295 & y=320)
    font_path = "/System/Library/Fonts/SFNS.ttf"
    if not os.path.exists(font_path):
        font_path = "/System/Library/Fonts/Helvetica.ttc"

    try:
        font_title = ImageFont.truetype(font_path, int(15 * scale))
        font_sub = ImageFont.truetype(font_path, int(12 * scale))
    except Exception:
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    text_main = "Drag Antigravity Chat Migrator to Applications"
    text_sub = "Перетащите Antigravity Chat Migrator в папку «Программы»"

    tb_main = draw.textbbox((0, 0), text_main, font=font_title)
    w_main = tb_main[2] - tb_main[0]
    draw.text(
        ((width - w_main) / 2, 305 * scale),
        text_main,
        font=font_title,
        fill=(255, 255, 255, 230),
    )

    tb_sub = draw.textbbox((0, 0), text_sub, font=font_sub)
    w_sub = tb_sub[2] - tb_sub[0]
    draw.text(
        ((width - w_sub) / 2, 330 * scale),
        text_sub,
        font=font_sub,
        fill=(255, 255, 255, 140),
    )

    return img


def build_background(assets_dir: Path) -> Path:
    assets_dir.mkdir(parents=True, exist_ok=True)
    path_1x = assets_dir / "dmg_background.png"
    path_2x = assets_dir / "dmg_background@2x.png"
    path_tiff = assets_dir / "dmg_background.tiff"

    img_1x = draw_artwork(660, 440, scale=1)
    img_1x.save(path_1x, "PNG")

    img_2x = draw_artwork(1320, 880, scale=2)
    img_2x.save(path_2x, "PNG")

    subprocess.run(
        ["/usr/bin/tiffutil", "-cathidpicheck", str(path_1x), str(path_2x), "-out", str(path_tiff)],
        check=True,
    )
    print(f"Generated Retina TIFF: {path_tiff}")
    return path_tiff


if __name__ == "__main__":
    assets = Path(__file__).resolve().parent.parent / "assets"
    build_background(assets)
