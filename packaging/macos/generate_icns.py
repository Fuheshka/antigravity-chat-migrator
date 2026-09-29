#!/usr/bin/env python3
"""Generate Apple HIG-compliant AppIcon.icns from 1024x1024 PNG source."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
from PIL import Image

def generate_icns(src_png: Path, out_icns: Path) -> None:
    if not src_png.exists():
        raise FileNotFoundError(f"Source icon not found: {src_png}")

    iconset_dir = out_icns.parent / f"{out_icns.stem}.iconset"
    iconset_dir.mkdir(parents=True, exist_ok=True)

    img = Image.open(src_png).convert("RGBA")

    sizes = [
        (16, "icon_16x16.png"),
        (32, "icon_16x16@2x.png"),
        (32, "icon_32x32.png"),
        (64, "icon_32x32@2x.png"),
        (128, "icon_128x128.png"),
        (256, "icon_128x128@2x.png"),
        (256, "icon_256x256.png"),
        (512, "icon_256x256@2x.png"),
        (512, "icon_512x512.png"),
        (1024, "icon_512x512@2x.png"),
    ]

    for dim, fname in sizes:
        resized = img.resize((dim, dim), Image.Resampling.LANCZOS)
        resized.save(iconset_dir / fname)

    out_icns.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["iconutil", "-c", "icns", str(iconset_dir), "-o", str(out_icns)], check=True)
    shutil.rmtree(iconset_dir)
    print(f"Generated {out_icns}")

if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent
    src = base_dir / "assets" / "AppIcon.png"
    out = base_dir / "assets" / "AppIcon.icns"
    generate_icns(src, out)
