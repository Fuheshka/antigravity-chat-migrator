"""Lightweight cross-platform GitHub Release update checker module.

Implements app-update-checker standard using Python standard library:
- 24-hour rate limit protection against GitHub 60 req/h IP quota
- SemVer comparison (is_version_newer)
- Platform-specific binary matching (.dmg on macOS, .exe/.zip on Windows, etc.)
- Silent failure in background mode
- Browser release launcher
"""

from __future__ import annotations

import json
from pathlib import Path
import platform
import sys
import time
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request
import webbrowser

from antigravity_migrator import __version__

DEFAULT_REPO = "Fuheshka/antigravity-chat-migrator"
DEFAULT_CACHE_FILE = Path.home() / ".antigravity-migrator" / "last_update_check.json"
COOLDOWN_SECONDS = 86400.0  # 24 hours
REQUEST_TIMEOUT_SECONDS = 4.0


def is_version_newer(candidate: str, current: str) -> bool:
    """Compare two semantic version strings numerically.

    Strips leading 'v' or 'V' and compares segments:
    e.g. 0.2.0 > 0.1.0, 1.10.0 > 1.9.5, 2.0.0 > 1.99.99.
    """
    def parse_segments(v: str) -> List[int]:
        cleaned = v.strip().lstrip("vV")
        segments: List[int] = []
        for part in cleaned.split("."):
            digits = "".join(c for c in part if c.isdigit())
            segments.append(int(digits) if digits else 0)
        return segments

    p1 = parse_segments(candidate)
    p2 = parse_segments(current)
    max_len = max(len(p1), len(p2))
    p1 += [0] * (max_len - len(p1))
    p2 += [0] * (max_len - len(p2))
    return p1 > p2


def get_platform_asset_url(
    assets: List[Dict[str, Any]],
    html_fallback: str,
    target_os: Optional[str] = None,
) -> str:
    """Find the best binary asset for the current OS from GitHub Release assets.

    Priorities:
    - macOS (Darwin): .dmg -> .zip -> .tar.gz
    - Windows: .exe -> .msi -> .zip
    - Linux: .AppImage -> .deb -> .rpm -> .tar.gz
    - Fallback: html_fallback
    """
    if not assets:
        return html_fallback

    system_name = (target_os or platform.system()).lower()

    if "darwin" in system_name or "mac" in system_name:
        priority_exts = [".dmg", ".zip", ".tar.gz"]
    elif "win" in system_name:
        priority_exts = [".exe", ".msi", ".zip"]
    elif "linux" in system_name:
        priority_exts = [".appimage", ".deb", ".rpm", ".tar.gz"]
    else:
        priority_exts = [".zip", ".tar.gz"]

    for ext in priority_exts:
        for asset in assets:
            name = str(asset.get("name", "")).lower()
            if name.endswith(ext):
                url = asset.get("browser_download_url")
                if url:
                    return str(url)

    return html_fallback


def check_github_update(
    repo: str = DEFAULT_REPO,
    current_version: str = __version__,
    force: bool = False,
    cache_file: Optional[Path] = None,
    timeout: float = REQUEST_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Check for latest release on GitHub with 24-hour rate limit protection.

    Args:
        repo: GitHub repository in 'owner/repo' format.
        current_version: Current application version string.
        force: If True, bypasses 24h cooldown and checks immediately.
        cache_file: Path to local timestamp cache file.
        timeout: Network request timeout in seconds (default 4s).

    Returns:
        Dict containing update availability, latest version, download URL,
        release notes, and check status.
    """
    cache_path = cache_file or DEFAULT_CACHE_FILE
    now = time.time()

    # 1. Check local cache cooldown when not forced
    if not force and cache_path.exists():
        try:
            content = cache_path.read_text(encoding="utf-8")
            data = json.loads(content)
            last_check = float(data.get("last_check", 0.0))
            if now - last_check < COOLDOWN_SECONDS:
                latest = str(data.get("latest_version", current_version))
                return {
                    "update_available": is_version_newer(latest, current_version),
                    "current_version": current_version,
                    "latest_version": latest,
                    "download_url": str(data.get("download_url", "")),
                    "release_notes": str(data.get("release_notes", "")),
                    "published_at": str(data.get("published_at", "")),
                    "throttled": True,
                    "checked": False,
                    "error": None,
                }
        except Exception:
            # Corrupted cache file: continue with fresh request
            pass

    # 2. Prepare HTTP request
    api_url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(
        api_url,
        headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"antigravity-chat-migrator/{current_version}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status_code = getattr(resp, "status", 200)
            if status_code == 200:
                raw_bytes = resp.read()
                release_data = json.loads(raw_bytes.decode("utf-8"))

                tag_name = str(release_data.get("tag_name", "")).strip()
                latest_version = tag_name.lstrip("vV")
                html_url = str(release_data.get("html_url", ""))
                notes = str(release_data.get("body", ""))
                published_at = str(release_data.get("published_at", ""))
                assets = release_data.get("assets", [])

                download_url = get_platform_asset_url(assets, html_fallback=html_url)
                newer = is_version_newer(latest_version, current_version)

                # Persist check timestamp to cache
                try:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_payload = {
                        "last_check": now,
                        "latest_version": latest_version,
                        "download_url": download_url,
                        "html_url": html_url,
                        "release_notes": notes,
                        "published_at": published_at,
                    }
                    cache_path.write_text(json.dumps(cache_payload, indent=2), encoding="utf-8")
                except Exception:
                    # Non-fatal if cache cannot be written
                    pass

                return {
                    "update_available": newer,
                    "current_version": current_version,
                    "latest_version": latest_version,
                    "download_url": download_url,
                    "release_notes": notes,
                    "published_at": published_at,
                    "throttled": False,
                    "checked": True,
                    "error": None,
                }

    except Exception as e:
        # Background check fails silently; manual check reports error
        if not force:
            return {
                "update_available": False,
                "current_version": current_version,
                "latest_version": current_version,
                "download_url": "",
                "release_notes": "",
                "published_at": "",
                "throttled": False,
                "checked": False,
                "error": None,
            }
        return {
            "update_available": False,
            "current_version": current_version,
            "latest_version": current_version,
            "download_url": "",
            "release_notes": "",
            "published_at": "",
            "throttled": False,
            "checked": False,
            "error": str(e),
        }

    return {
        "update_available": False,
        "current_version": current_version,
        "latest_version": current_version,
        "download_url": "",
        "release_notes": "",
        "published_at": "",
        "throttled": False,
        "checked": False,
        "error": None,
    }


def open_update_url(url: str) -> bool:
    """Open release download page in the default web browser."""
    if not url:
        return False
    try:
        return bool(webbrowser.open(url))
    except Exception:
        return False
