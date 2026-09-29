import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from antigravity_migrator.paths import PathManager


class TestPathManager(unittest.TestCase):
    def test_default_paths_on_macos(self):
        fake_home = Path("/Users/testuser")
        with patch("platform.system", return_value="Darwin"), \
             patch.object(Path, "home", return_value=fake_home), \
             patch.dict(os.environ, {}, clear=True):
            pm = PathManager()
            self.assertEqual(pm.system, "Darwin")
            self.assertEqual(pm.data_dir, fake_home / ".gemini" / "antigravity")
            self.assertEqual(pm.config_dir, fake_home / ".gemini" / "config")
            self.assertEqual(pm.projects_dir, fake_home / ".gemini" / "config" / "projects")
            self.assertEqual(pm.conversations_dir, fake_home / ".gemini" / "antigravity" / "conversations")
            self.assertEqual(pm.annotations_dir, fake_home / ".gemini" / "antigravity" / "annotations")
            self.assertEqual(pm.brain_dir, fake_home / ".gemini" / "antigravity" / "brain")
            self.assertEqual(pm.summaries_pb, fake_home / ".gemini" / "antigravity" / "agyhub_summaries_proto.pb")
            self.assertEqual(pm.summaries_db, fake_home / ".gemini" / "antigravity" / "conversation_summaries.db")

    def test_default_paths_on_windows(self):
        fake_home = Path("C:/Users/testuser")
        with patch("platform.system", return_value="Windows"), \
             patch.object(Path, "home", return_value=fake_home), \
             patch.dict(os.environ, {}, clear=True):
            pm = PathManager()
            self.assertEqual(pm.system, "Windows")
            self.assertEqual(pm.data_dir, fake_home / ".gemini" / "antigravity")
            self.assertEqual(pm.config_dir, fake_home / ".gemini" / "config")
            self.assertEqual(pm.projects_dir, fake_home / ".gemini" / "config" / "projects")

    def test_environment_variable_overrides(self):
        custom_data = "/tmp/custom_data"
        custom_config = "/tmp/custom_config"
        env = {
            "GEMINI_DATA_DIR": custom_data,
            "GEMINI_CONFIG_DIR": custom_config,
        }
        with patch.dict(os.environ, env, clear=True):
            pm = PathManager()
            self.assertEqual(pm.data_dir, Path(custom_data))
            self.assertEqual(pm.config_dir, Path(custom_config))
            self.assertEqual(pm.projects_dir, Path(custom_config) / "projects")
            self.assertEqual(pm.conversations_dir, Path(custom_data) / "conversations")

    def test_explicit_argument_overrides(self):
        explicit_data = Path("/tmp/explicit_data")
        explicit_config = Path("/tmp/explicit_config")
        pm = PathManager(data_dir=explicit_data, config_dir=explicit_config)
        self.assertEqual(pm.data_dir, explicit_data)
        self.assertEqual(pm.config_dir, explicit_config)
        self.assertEqual(pm.projects_dir, explicit_config / "projects")

    def test_normalize_uri_macos(self):
        pm = PathManager(system="Darwin")
        uri = pm.normalize_uri("/Users/testuser/Documents/project")
        self.assertEqual(uri, "file:///Users/testuser/Documents/project")

        already_uri = "file:///Users/testuser/Documents/project"
        self.assertEqual(pm.normalize_uri(already_uri), already_uri)

    def test_normalize_uri_windows(self):
        pm = PathManager(system="Windows")
        uri = pm.normalize_uri(r"C:\Users\testuser\Projects\my-app")
        self.assertEqual(uri, "file:///C:/Users/testuser/Projects/my-app")

    def test_uri_to_path_macos(self):
        pm = PathManager(system="Darwin")
        path = pm.uri_to_path("file:///Users/testuser/Documents/project")
        self.assertEqual(path, Path("/Users/testuser/Documents/project"))

    def test_uri_to_path_windows(self):
        pm = PathManager(system="Windows")
        path = pm.uri_to_path("file:///C:/Users/testuser/Projects/my-app")
        self.assertEqual(path, Path("C:/Users/testuser/Projects/my-app"))

    def test_ensure_dirs(self, tmp_path=None):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            data_dir = base / "data"
            config_dir = base / "config"
            pm = PathManager(data_dir=data_dir, config_dir=config_dir)
            pm.ensure_dirs()
            self.assertTrue(pm.data_dir.is_dir())
            self.assertTrue(pm.config_dir.is_dir())
            self.assertTrue(pm.projects_dir.is_dir())
            self.assertTrue(pm.conversations_dir.is_dir())
            self.assertTrue(pm.annotations_dir.is_dir())
            self.assertTrue(pm.brain_dir.is_dir())
            self.assertTrue(pm.backups_dir.is_dir())


if __name__ == "__main__":
    unittest.main()
