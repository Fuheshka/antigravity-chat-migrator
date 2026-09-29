#!/usr/bin/env python3
"""Generate Windows multi-resolution AppIcon.ico from 1024x1024 PNG source."""

from pathlib import Path
from PIL import Image


def generate_ico(src_png: Path, out_ico: Path) -> None:
    """Generate multi-resolution .ico file from source PNG."""
    if not src_png.exists():
        raise FileNotFoundError(f"Source icon not found: {src_png}")

    out_ico.parent.mkdir(parents=True, exist_ok=True)
    img = Image.open(src_png).convert("RGBA")
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(out_ico, format="ICO", sizes=sizes)
    print(f"Generated {out_ico} ({out_ico.stat().st_size} bytes)")


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent
    src = base_dir / "assets" / "AppIcon.png"
    out = base_dir / "assets" / "AppIcon.ico"
    generate_ico(src, out)
