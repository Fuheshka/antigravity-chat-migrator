#!/usr/bin/env python3
"""Build and finalize Apple HIG-compliant macOS DMG installer disk image."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

try:
    from build_dmg_background import build_background
except ImportError:
    from packaging.macos.build_dmg_background import build_background


def run_cmd(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run shell command and return CompletedProcess."""
    print(f"--> {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def finalize_dmg(dmg_path: Path, vol_name: str, app_name: str) -> None:
    """Mount RW image, hide service files, lock Finder window bounds, and eliminate scrollbars."""
    print(f"\n=== Finalizing DMG Layout & Locking Finder Bounds for {dmg_path.name} ===")
    dist_dir = dmg_path.parent
    rw_dmg = dist_dir / "temp_rw.dmg"

    if rw_dmg.exists():
        rw_dmg.unlink()

    run_cmd(["hdiutil", "convert", str(dmg_path), "-format", "UDRW", "-o", str(rw_dmg)])

    # Mount temporary read-write DMG
    mount_res = run_cmd(["hdiutil", "attach", str(rw_dmg), "-noautoopen", "-nobrowse"])
    mount_output = mount_res.stdout
    dev_name = ""
    mount_point = f"/Volumes/{vol_name}"

    for line in mount_output.splitlines():
        if "/Volumes/" in line:
            parts = line.split("\t")
            dev_name = parts[0].strip()
            mount_point = parts[-1].strip()

    print(f"Mounted RW volume at: {mount_point} ({dev_name})")

    # Apply chflags hidden & SetFile -a V to all hidden items
    hidden_files = [".background", ".VolumeIcon.icns", ".DS_Store", ".Trashes", ".fseventsd"]
    for hf in hidden_files:
        full_p = Path(mount_point) / hf
        if full_p.exists():
            subprocess.run(["chflags", "hidden", str(full_p)], check=False)
            subprocess.run(["SetFile", "-a", "V", str(full_p)], check=False)

    # Hide extension on app bundle inside DMG volume
    app_full_p = Path(mount_point) / app_name
    if app_full_p.exists():
        subprocess.run(["SetFile", "-a", "E", str(app_full_p)], check=False)

    # AppleScript to position hidden items slightly below window (y=500, NOT right)
    # and lock window bounds to 660x440 (200, 120, 860, 560)
    applescript_code = f"""
    tell application "Finder"
        tell disk "{vol_name}"
            open
            tell container window
                set current view to icon view
                set toolbar visible to false
                set statusbar visible to false
                set bounds to {{200, 120, 860, 560}}
            end tell

            -- Set explicit positions for app and Applications link
            try
                set position of item "{app_name}" to {{160, 140}}
            end try
            try
                set position of item "Applications" to {{500, 140}}
            end try

            -- Position hidden items slightly below window bounds (y=500)
            -- so they NEVER cause horizontal rightward scrolling
            try
                set position of item ".background" to {{330, 500}}
            end try
            try
                set position of item ".VolumeIcon.icns" to {{330, 500}}
            end try

            set opts to icon view options of container window
            tell opts
                set icon size to 128
                set text size to 12
                set arrangement to not arranged
                set label position to bottom
            end tell
            update without registering applications
            close
        end tell
    end tell
    """

    try:
        run_cmd(["osascript", "-e", applescript_code], check=False)
        time.sleep(2)
    except Exception as e:
        print(f"Notice: AppleScript execution warning (acceptable in headless CI): {e}")

    # Detach RW volume
    if dev_name:
        run_cmd(["hdiutil", "detach", dev_name, "-force"])
    time.sleep(1)

    # Compress RW DMG back to final read-only DMG with UDZO max compression
    if dmg_path.exists():
        dmg_path.unlink()

    run_cmd([
        "hdiutil",
        "convert",
        str(rw_dmg),
        "-format",
        "UDZO",
        "-imagekey",
        "zlib-level=9",
        "-o",
        str(dmg_path),
    ])

    if rw_dmg.exists():
        rw_dmg.unlink()

    print(f"🎉 DMG Finalization Complete: {dmg_path}")


def create_dmg(
    source_app: Path,
    output_dmg: Path,
    vol_name: str = "Antigravity Chat Migrator",
    icon_path: Path | None = None,
    background_tiff: Path | None = None,
) -> Path:
    """Create styled macOS DMG disk image."""
    output_dmg.parent.mkdir(parents=True, exist_ok=True)
    if output_dmg.exists():
        output_dmg.unlink()

    # Ensure background artwork is available
    if background_tiff is None or not background_tiff.exists():
        assets_dir = output_dmg.parent.parent.parent / "packaging" / "assets"
        background_tiff = build_background(assets_dir)

    has_create_dmg = shutil.which("create-dmg") is not None

    if has_create_dmg:
        print("Using create-dmg utility...")
        cmd = [
            "create-dmg",
            "--overwrite",
            "--volname",
            vol_name,
            "--window-pos",
            "200",
            "120",
            "--window-size",
            "660",
            "440",
            "--app-drop-link",
            "500",
            "140",
            "--icon",
            source_app.name,
            "160",
            "140",
            "--hide-extension",
            source_app.name,
        ]

        if icon_path and icon_path.exists():
            cmd.extend(["--volicon", str(icon_path)])

        if background_tiff and background_tiff.exists():
            cmd.extend(["--background", str(background_tiff)])

        cmd.extend([str(output_dmg), str(source_app)])

        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            print("create-dmg reported non-zero returncode, falling back to native hdiutil...")
            has_create_dmg = False

    if not has_create_dmg:
        print("Using native macOS hdiutil staging...")
        staging_dir = output_dmg.parent / "dmg_staging"
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        staging_dir.mkdir(parents=True, exist_ok=True)

        # Copy target app bundle or executable
        if source_app.is_dir():
            shutil.copytree(source_app, staging_dir / source_app.name)
        else:
            shutil.copy2(source_app, staging_dir / source_app.name)

        # Symlink /Applications
        os.symlink("/Applications", staging_dir / "Applications")

        # Copy background artwork
        if background_tiff and background_tiff.exists():
            bg_dest = staging_dir / ".background"
            bg_dest.mkdir(exist_ok=True)
            shutil.copy2(background_tiff, bg_dest / "dmg_background.tiff")

        # Copy volume icon
        if icon_path and icon_path.exists():
            shutil.copy2(icon_path, staging_dir / ".VolumeIcon.icns")

        # Create basic UDZO DMG
        subprocess.run(
            [
                "hdiutil",
                "create",
                "-volname",
                vol_name,
                "-srcfolder",
                str(staging_dir),
                "-ov",
                "-format",
                "UDZO",
                str(output_dmg),
            ],
            check=True,
        )
        shutil.rmtree(staging_dir)

    # Step 3: Finalize DMG bounds and scrollbar suppression
    finalize_dmg(output_dmg, vol_name, source_app.name)
    return output_dmg


def main() -> None:
    parser = argparse.ArgumentParser(description="Create styled DMG installer disk image for macOS.")
    parser.add_argument(
        "--app",
        type=Path,
        default=Path("dist/macos/Antigravity Chat Migrator.app"),
        help="Path to source application bundle or binary",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist/macos/Antigravity-Chat-Migrator-macOS.dmg"),
        help="Path to output DMG file",
    )
    parser.add_argument(
        "--volname",
        type=str,
        default="Antigravity Chat Migrator",
        help="Volume label inside Finder",
    )
    parser.add_argument(
        "--icon",
        type=Path,
        default=Path("packaging/assets/AppIcon.icns"),
        help="Path to volume icon (.icns)",
    )
    parser.add_argument(
        "--background",
        type=Path,
        default=Path("packaging/assets/dmg_background.tiff"),
        help="Path to multi-resolution Retina background TIFF",
    )

    args = parser.parse_args()

    app_path = args.app
    # If app bundle doesn't exist yet, check if standalone binary exists
    if not app_path.exists():
        candidate_bin = Path("dist/macos/agy-migrator")
        if candidate_bin.exists():
            app_path = candidate_bin

    if not app_path.exists():
        print(f"Error: Target app/binary not found at {args.app} or {candidate_bin}", file=sys.stderr)
        sys.exit(1)

    create_dmg(
        source_app=app_path,
        output_dmg=args.output,
        vol_name=args.volname,
        icon_path=args.icon if args.icon.exists() else None,
        background_tiff=args.background if args.background.exists() else None,
    )


if __name__ == "__main__":
    main()
