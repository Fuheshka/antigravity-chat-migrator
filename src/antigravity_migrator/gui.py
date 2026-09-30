"""Native desktop GUI window launcher for Antigravity Chat Migrator powered by pywebview."""

from __future__ import annotations

import logging
from pathlib import Path
import sys
from typing import Any, Optional

try:
    import webview
except ImportError as err:  # pragma: no cover
    webview = None  # type: ignore[assignment]
    _import_err = err
else:
    _import_err = None  # type: ignore[assignment]

from antigravity_migrator.gui_api import GuiBridgeApi

logger = logging.getLogger(__name__)

__all__ = ["launch_gui", "get_gui_asset_dir", "get_gui_index_path"]


def get_gui_asset_dir() -> Path:
    """Resolve directory containing HTML, CSS, and JS frontend assets.

    Supports both development source tree and PyInstaller frozen bundle (_MEIPASS).
    """
    # 1. PyInstaller frozen application support
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundle_gui = Path(meipass) / "antigravity_migrator" / "gui"
        if bundle_gui.exists():
            return bundle_gui
        bundle_alt = Path(meipass) / "gui"
        if bundle_alt.exists():
            return bundle_alt

    # 2. Local package directory
    pkg_gui = Path(__file__).resolve().parent / "gui"
    if pkg_gui.exists():
        return pkg_gui

    # 3. Fallback to current working directory
    cwd_gui = Path.cwd() / "src" / "antigravity_migrator" / "gui"
    if cwd_gui.exists():
        return cwd_gui

    raise FileNotFoundError(
        f"Antigravity GUI frontend assets directory not found. Searched: {pkg_gui}"
    )


def get_gui_index_path() -> Path:
    """Resolve absolute path to index.html frontend file."""
    index_path = get_gui_asset_dir() / "index.html"
    if not index_path.exists():
        raise FileNotFoundError(
            f"Antigravity GUI index.html not found at: {index_path}"
        )
    return index_path


def launch_gui(
    title: str = "Antigravity Chat Migrator",
    width: int = 1024,
    height: int = 720,
    debug: bool = False,
    api: Optional[GuiBridgeApi] = None,
    start_loop: bool = True,
) -> Any:
    """Create and launch native desktop WebKit (macOS) / WebView2 (Windows) window.

    Args:
        title: Window title string.
        width: Initial window width in pixels (default 1024).
        height: Initial window height in pixels (default 720).
        debug: Enable developer tools / web inspector.
        api: Optional GuiBridgeApi instance; if None, instantiates default GuiBridgeApi().
        start_loop: Whether to invoke webview.start() (blocking). Set to False for testing.

    Returns:
        The created pywebview.Window instance.
    """
    if webview is None:
        raise RuntimeError(
            "pywebview is required to run the Antigravity GUI. "
            "Please install it with: pip install 'pywebview>=5.0.0'"
        ) from _import_err

    index_path = get_gui_index_path()
    bridge_api = api if api is not None else GuiBridgeApi()

    # Create native window with minimum 800x560, dark theme, and centered position
    window = webview.create_window(
        title=title,
        url=str(index_path),
        js_api=bridge_api,
        width=width,
        height=height,
        x=None,
        y=None,
        min_size=(800, 560),
        resizable=True,
        background_color="#0d1117",
        text_select=True,
    )

    if start_loop:
        webview.start(debug=debug)

    return window
