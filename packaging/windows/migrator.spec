# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification file for Antigravity Chat Migrator dual Windows binaries."""

import os
import sys
from pathlib import Path

# Determine project root relative to this spec file
SPEC_DIR = Path(__file__).resolve().parent if '__file__' in globals() else Path(os.getcwd())
if (SPEC_DIR / "entrypoint.py").exists():
    BASE_DIR = SPEC_DIR.parent.parent
    ENTRYPOINT_CLI = str(SPEC_DIR / "entrypoint.py")
    ENTRYPOINT_GUI = str(SPEC_DIR / "gui_entrypoint.py")
    assets_dir = SPEC_DIR.parent / "assets"
    ico_file = assets_dir / "app.ico" if (assets_dir / "app.ico").exists() else assets_dir / "AppIcon.ico"
    ICON_PATH = str(ico_file)
else:
    BASE_DIR = Path(os.getcwd())
    ENTRYPOINT_CLI = str(BASE_DIR / "packaging" / "windows" / "entrypoint.py")
    ENTRYPOINT_GUI = str(BASE_DIR / "packaging" / "windows" / "gui_entrypoint.py")
    assets_dir = BASE_DIR / "packaging" / "assets"
    ico_file = assets_dir / "app.ico" if (assets_dir / "app.ico").exists() else assets_dir / "AppIcon.ico"
    ICON_PATH = str(ico_file)

SRC_DIR = str(BASE_DIR / "src")

block_cipher = None

a = Analysis(
    [ENTRYPOINT_GUI, ENTRYPOINT_CLI],
    pathex=[SRC_DIR],
    binaries=[],
    datas=[
        (str(BASE_DIR / "src" / "antigravity_migrator" / "gui"), "antigravity_migrator/gui"),
    ],
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
        "webview",
        "webview.platforms.winforms",
        "webview.platforms.edgechromium",
        "antigravity_migrator",
        "antigravity_migrator.annotation_generator",
        "antigravity_migrator.backup_manager",
        "antigravity_migrator.cli",
        "antigravity_migrator.db_manager",
        "antigravity_migrator.gui",
        "antigravity_migrator.gui_api",
        "antigravity_migrator.i18n",
        "antigravity_migrator.paths",
        "antigravity_migrator.process_watcher",
        "antigravity_migrator.project_registry",
        "antigravity_migrator.proto_codec",
        "antigravity_migrator.service",
        "antigravity_migrator.ui_renderer",
        "antigravity_migrator.updater",
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

# Filter scripts for each target to designate entrypoint while preserving runtime hooks
scripts_gui = [s for s in a.scripts if s[0] != "entrypoint"]
scripts_cli = [s for s in a.scripts if s[0] != "gui_entrypoint"]

exe_gui = EXE(
    pyz,
    scripts_gui,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Antigravity Chat Migrator.exe",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_PATH if os.path.exists(ICON_PATH) else None,
)

exe_cli = EXE(
    pyz,
    scripts_cli,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="agy-migrator.exe",
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
