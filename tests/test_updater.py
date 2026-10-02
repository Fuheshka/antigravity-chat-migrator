"""Tests for the GitHub Release update checker module (app-update-checker standard)."""

from __future__ import annotations

import json
from pathlib import Path
import time
from unittest.mock import MagicMock, patch
import urllib.error
import pytest

from antigravity_migrator.updater import (
    check_github_update,
    get_platform_asset_url,
    is_version_newer,
    open_update_url,
)


class TestSemVerComparison:
    """Tests for is_version_newer semantic version comparator."""

    def test_newer_minor_and_patch(self):
        assert is_version_newer("0.2.0", "0.1.0") is True
        assert is_version_newer("0.1.1", "0.1.0") is True
        assert is_version_newer("1.0.0", "0.9.9") is True
        assert is_version_newer("1.10.0", "1.9.5") is True
        assert is_version_newer("2.0.0", "1.99.99") is True

    def test_same_version(self):
        assert is_version_newer("0.1.0", "0.1.0") is False
        assert is_version_newer("1.2.3", "1.2.3") is False
        assert is_version_newer("v0.1.0", "0.1.0") is False
        assert is_version_newer("0.1.0", "v0.1.0") is False

    def test_older_version(self):
        assert is_version_newer("0.1.0", "0.2.0") is False
        assert is_version_newer("0.0.9", "0.1.0") is False
        assert is_version_newer("1.9.5", "1.10.0") is False

    def test_strip_v_prefix(self):
        assert is_version_newer("v0.2.0", "0.1.0") is True
        assert is_version_newer("V1.0.0", "0.9.0") is True
        assert is_version_newer("v1.5.0", "v1.4.9") is True

    def test_variable_length_segments(self):
        assert is_version_newer("1.2.1", "1.2") is True
        assert is_version_newer("1.2", "1.2.0") is False
        assert is_version_newer("1.2.0.1", "1.2.0") is True


class TestPlatformAssetUrl:
    """Tests for platform-specific asset prioritization."""

    def test_macos_asset_matching(self):
        assets = [
            {"name": "antigravity-chat-migrator-windows.zip", "browser_download_url": "https://example.com/win.zip"},
            {"name": "AntigravityMigrator-0.2.0.dmg", "browser_download_url": "https://example.com/mac.dmg"},
            {"name": "source.tar.gz", "browser_download_url": "https://example.com/source.tar.gz"},
        ]
        url = get_platform_asset_url(assets, html_fallback="https://example.com/release", target_os="Darwin")
        assert url == "https://example.com/mac.dmg"

    def test_windows_asset_matching(self):
        assets = [
            {"name": "AntigravityMigrator-Setup.exe", "browser_download_url": "https://example.com/setup.exe"},
            {"name": "AntigravityMigrator-portable.zip", "browser_download_url": "https://example.com/win.zip"},
            {"name": "AntigravityMigrator.dmg", "browser_download_url": "https://example.com/mac.dmg"},
        ]
        url = get_platform_asset_url(assets, html_fallback="https://example.com/release", target_os="Windows")
        assert url == "https://example.com/setup.exe"

    def test_linux_asset_matching(self):
        assets = [
            {"name": "AntigravityMigrator.AppImage", "browser_download_url": "https://example.com/app.AppImage"},
            {"name": "antigravity-migrator.deb", "browser_download_url": "https://example.com/app.deb"},
        ]
        url = get_platform_asset_url(assets, html_fallback="https://example.com/release", target_os="Linux")
        assert url == "https://example.com/app.AppImage"

    def test_fallback_when_no_assets_match(self):
        assets = [
            {"name": "unknown-format.bin", "browser_download_url": "https://example.com/bin"},
        ]
        url = get_platform_asset_url(assets, html_fallback="https://example.com/releases/tag/v0.2.0", target_os="Darwin")
        assert url == "https://example.com/releases/tag/v0.2.0"

    def test_fallback_on_empty_assets(self):
        url = get_platform_asset_url([], html_fallback="https://example.com/fallback", target_os="Darwin")
        assert url == "https://example.com/fallback"


class TestCheckGithubUpdate:
    """Tests for check_github_update caching, cooldown, and network handling."""

    @pytest.fixture
    def cache_path(self, tmp_path: Path) -> Path:
        return tmp_path / "cache" / "last_update_check.json"

    def test_cooldown_throttles_background_check(self, cache_path: Path):
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        now = time.time()
        cache_data = {
            "last_check": now - 3600,  # 1 hour ago (within 24h)
            "latest_version": "0.1.0",
            "download_url": "https://example.com/dl",
            "release_notes": "No notes",
            "published_at": "2026-10-01T00:00:00Z",
        }
        cache_path.write_text(json.dumps(cache_data), encoding="utf-8")

        with patch("urllib.request.urlopen") as mock_urlopen:
            res = check_github_update(
                repo="Fuheshka/antigravity-chat-migrator",
                current_version="0.1.0",
                force=False,
                cache_file=cache_path,
            )
            mock_urlopen.assert_not_called()
            assert res["throttled"] is True
            assert res["update_available"] is False

    def test_cooldown_bypassed_when_forced(self, cache_path: Path):
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        now = time.time()
        cache_data = {
            "last_check": now - 100,
            "latest_version": "0.1.0",
        }
        cache_path.write_text(json.dumps(cache_data), encoding="utf-8")

        fake_release = {
            "tag_name": "v0.2.0",
            "html_url": "https://github.com/Fuheshka/antigravity-chat-migrator/releases/tag/v0.2.0",
            "body": "New feature release",
            "published_at": "2026-10-01T08:00:00Z",
            "assets": [
                {
                    "name": "AntigravityMigrator-0.2.0.dmg",
                    "browser_download_url": "https://github.com/.../AntigravityMigrator-0.2.0.dmg",
                },
                {
                    "name": "AntigravityMigrator-0.2.0-setup.exe",
                    "browser_download_url": "https://github.com/.../AntigravityMigrator-0.2.0-setup.exe",
                },
                {
                    "name": "AntigravityMigrator-0.2.0.AppImage",
                    "browser_download_url": "https://github.com/.../AntigravityMigrator-0.2.0.AppImage",
                },
            ],
        }

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(fake_release).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            res = check_github_update(
                repo="Fuheshka/antigravity-chat-migrator",
                current_version="0.1.0",
                force=True,
                cache_file=cache_path,
            )
            assert res["throttled"] is False
            assert res["update_available"] is True
            assert res["latest_version"] == "0.2.0"
            assert any(
                ext in res["download_url"].lower()
                for ext in ["dmg", "exe", "appimage"]
            )

            # Cache file should be updated
            saved_cache = json.loads(cache_path.read_text(encoding="utf-8"))
            assert saved_cache["latest_version"] == "0.2.0"
            assert abs(saved_cache["last_check"] - time.time()) < 5

    def test_cached_update_returned_during_cooldown(self, cache_path: Path):
        """When an update was previously discovered, cooldown still reports it as available."""
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        now = time.time()
        cache_data = {
            "last_check": now - 1800,  # 30 min ago
            "latest_version": "0.3.0",
            "download_url": "https://example.com/dl.dmg",
            "release_notes": "Huge release",
            "published_at": "2026-10-01T00:00:00Z",
        }
        cache_path.write_text(json.dumps(cache_data), encoding="utf-8")

        res = check_github_update(
            repo="Fuheshka/antigravity-chat-migrator",
            current_version="0.1.0",
            force=False,
            cache_file=cache_path,
        )
        assert res["throttled"] is True
        assert res["update_available"] is True
        assert res["latest_version"] == "0.3.0"
        assert res["download_url"] == "https://example.com/dl.dmg"

    def test_network_failure_silent_in_background(self, cache_path: Path):
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("DNS lookup failed")):
            res = check_github_update(
                repo="Fuheshka/antigravity-chat-migrator",
                current_version="0.1.0",
                force=False,
                cache_file=cache_path,
            )
            assert res["update_available"] is False
            assert res["checked"] is False
            assert res["error"] is None  # Fails silently in background

    def test_network_failure_reported_on_force(self, cache_path: Path):
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
            res = check_github_update(
                repo="Fuheshka/antigravity-chat-migrator",
                current_version="0.1.0",
                force=True,
                cache_file=cache_path,
            )
            assert res["update_available"] is False
            assert res["checked"] is False
            assert res["error"] is not None
            assert "Connection refused" in res["error"]


class TestOpenUpdateUrl:
    """Test browser launcher for release page."""

    def test_open_update_url(self):
        with patch("webbrowser.open", return_value=True) as mock_open:
            result = open_update_url("https://github.com/Fuheshka/antigravity-chat-migrator/releases")
            mock_open.assert_called_once_with("https://github.com/Fuheshka/antigravity-chat-migrator/releases")
            assert result is True
