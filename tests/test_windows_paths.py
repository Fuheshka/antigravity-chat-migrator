"""Tests for Windows path handling, backslash resilience, and %USERPROFILE% integration."""

import os
import tempfile
import unittest
from pathlib import Path, PureWindowsPath
from unittest.mock import patch

from antigravity_migrator.paths import PathManager
from antigravity_migrator.project_registry import (
    _uri_to_path,
    load_registered_projects,
    normalize_workspace_uri,
    register_new_project,
)


class TestWindowsPaths(unittest.TestCase):
    """Verify Windows filesystem paths, %USERPROFILE% resolution, and URI conversions."""

    def test_userprofile_path_resolution(self):
        """Verify PathManager resolves ~/.gemini via USERPROFILE on Windows."""
        fake_profile = r"C:\Users\Developer"
        fake_home = Path(fake_profile)

        with patch("platform.system", return_value="Windows"), \
             patch.object(Path, "home", return_value=fake_home), \
             patch.dict(os.environ, {"USERPROFILE": fake_profile}, clear=True):
            pm = PathManager()

            self.assertEqual(pm.system, "Windows")
            # Verify data and config root directories
            self.assertEqual(pm.data_dir, fake_home / ".gemini" / "antigravity")
            self.assertEqual(pm.config_dir, fake_home / ".gemini" / "config")
            self.assertEqual(pm.projects_dir, fake_home / ".gemini" / "config" / "projects")
            self.assertEqual(pm.conversations_dir, fake_home / ".gemini" / "antigravity" / "conversations")
            self.assertEqual(pm.annotations_dir, fake_home / ".gemini" / "antigravity" / "annotations")
            self.assertEqual(pm.brain_dir, fake_home / ".gemini" / "antigravity" / "brain")
            self.assertEqual(pm.summaries_db, fake_home / ".gemini" / "antigravity" / "conversation_summaries.db")
            self.assertEqual(pm.summaries_pb, fake_home / ".gemini" / "antigravity" / "agyhub_summaries_proto.pb")
            self.assertEqual(pm.backups_dir, fake_home / ".gemini" / "antigravity" / ".backups")

    def test_normalize_uri_with_windows_backslashes(self):
        """Verify backslashed Windows paths are normalized to canonical file:/// URIs."""
        pm = PathManager(system="Windows")

        # Standard drive letter with backslashes
        raw_path = r"C:\Users\Developer\.gemini\antigravity\conversations\abc-123.db"
        expected_uri = "file:///C:/Users/Developer/.gemini/antigravity/conversations/abc-123.db"
        self.assertEqual(pm.normalize_uri(raw_path), expected_uri)

        # Path with spaces
        raw_spaces = r"D:\Work Spaces\Project Alpha\sub folder"
        expected_spaces = "file:///D:/Work Spaces/Project Alpha/sub folder"
        self.assertEqual(pm.normalize_uri(raw_spaces), expected_spaces)

        # Lowercase drive letter should preserve or normalize cleanly
        raw_lower = r"c:\tools\gemini"
        self.assertEqual(pm.normalize_uri(raw_lower), "file:///c:/tools/gemini")

    def test_uri_to_path_windows_roundtrip(self):
        """Verify URI converts back to local Windows Path accurately."""
        pm = PathManager(system="Windows")
        uri = "file:///C:/Users/Developer/.gemini/antigravity/conversations/abc-123.db"
        path = pm.uri_to_path(uri)
        self.assertEqual(path, Path("C:/Users/Developer/.gemini/antigravity/conversations/abc-123.db"))

    def test_project_registry_windows_uri_normalization(self):
        """Verify normalize_workspace_uri handles Windows backslashes and drive capitalization."""
        # Standard backslash path
        win_path = r"C:\Users\Developer\Documents\GitHub\my-app"
        normalized = normalize_workspace_uri(win_path)
        self.assertEqual(normalized, "file:///C:/Users/Developer/Documents/GitHub/my-app")

        # Lowercase drive letter gets capitalized
        win_lower = r"d:\projects\game_engine\\"
        normalized_lower = normalize_workspace_uri(win_lower)
        self.assertEqual(normalized_lower, "file:///D:/projects/game_engine")

        # Mixed slashes
        win_mixed = "C:/Users/Developer\\Documents/Project"
        self.assertEqual(normalize_workspace_uri(win_mixed), "file:///C:/Users/Developer/Documents/Project")

        # Conversion back to Path via _uri_to_path
        roundtrip_path = _uri_to_path(normalized)
        self.assertEqual(roundtrip_path, Path("C:/Users/Developer/Documents/GitHub/my-app"))

    def test_project_registry_save_and_load_with_windows_paths(self):
        """Verify saving and loading project descriptors with Windows URIs and names."""
        with tempfile.TemporaryDirectory() as td:
            config_dir = Path(td)
            win_uri = "file:///C:/Users/Developer/Desktop/UnityGame"

            # Save project descriptor
            proj_id = register_new_project(config_dir, win_uri, project_name="UnityGame")
            self.assertTrue(proj_id)

            # Load registered projects
            registry = load_registered_projects(config_dir)
            self.assertIn(win_uri, registry)
            self.assertEqual(registry[win_uri], proj_id)


if __name__ == "__main__":
    unittest.main()
