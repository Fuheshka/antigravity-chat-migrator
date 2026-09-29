# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification file for agy-migrator standalone binary."""

import os
import sys
from pathlib import Path

# Determine project root relative to this spec file
SPEC_DIR = Path(__file__).resolve().parent if '__file__' in globals() else Path(os.getcwd())
if (SPEC_DIR / "entrypoint.py").exists():
    BASE_DIR = SPEC_DIR.parent.parent
    ENTRYPOINT = str(SPEC_DIR / "entrypoint.py")
    ICON_PATH = str(SPEC_DIR.parent / "assets" / "AppIcon.icns")
else:
    BASE_DIR = Path(os.getcwd())
    ENTRYPOINT = str(BASE_DIR / "packaging" / "macos" / "entrypoint.py")
    ICON_PATH = str(BASE_DIR / "packaging" / "assets" / "AppIcon.icns")

SRC_DIR = str(BASE_DIR / "src")

block_cipher = None

a = Analysis(
    [ENTRYPOINT],
    pathex=[SRC_DIR],
    binaries=[],
    datas=[],
    hiddenimports=[
        "typer",
        "typer.core",
        "click",
        "rich",
        "rich.box",
        "rich.console",
        "rich.table",
        "rich.text",
        "rich.panel",
        "psutil",
        "sqlite3",
        "antigravity_migrator",
        "antigravity_migrator.annotation_generator",
        "antigravity_migrator.backup_manager",
        "antigravity_migrator.cli",
        "antigravity_migrator.db_manager",
        "antigravity_migrator.i18n",
        "antigravity_migrator.paths",
        "antigravity_migrator.process_watcher",
        "antigravity_migrator.project_registry",
        "antigravity_migrator.proto_codec",
        "antigravity_migrator.service",
        "antigravity_migrator.ui_renderer",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy", "numpy", "pytest", "PIL"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="agy-migrator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_PATH if os.path.exists(ICON_PATH) else None,
)
