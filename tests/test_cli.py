import gc
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from antigravity_migrator.cli import app
from antigravity_migrator.proto_codec import build_workspace_info, encode_field


def _create_mock_conversation(db_path: Path, workspace_uri: str, project_id: str | None = None) -> None:
    """Helper to create a mock SQLite conversation database."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    parts = []
    if workspace_uri:
        parts.append(encode_field(1, 2, build_workspace_info(workspace_uri)))
        parts.append(encode_field(7, 2, workspace_uri.encode("utf-8")))
    if project_id:
        parts.append(encode_field(18, 2, project_id.encode("utf-8")))

    blob = b"".join(parts)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS trajectory_metadata_blob (id TEXT PRIMARY KEY, data BLOB)")
        conn.execute("INSERT OR REPLACE INTO trajectory_metadata_blob (id, data) VALUES ('main', ?)", (blob,))
        conn.commit()
    finally:
        conn.close()


class TestCliCommands(unittest.TestCase):
    """Test suite for agy-migrator CLI."""

    def setUp(self) -> None:
        self.runner = CliRunner()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.data_dir = self.root / "gemini" / "antigravity"
        self.config_dir = self.root / "gemini" / "config"
        self.conv_dir = self.data_dir / "conversations"
        self.ann_dir = self.data_dir / "annotations"
        self.backups_dir = self.data_dir / ".backups"

        self.conv_dir.mkdir(parents=True, exist_ok=True)
        self.ann_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.patcher = patch("antigravity_migrator.cli.is_antigravity_running", return_value=False)
        self.mock_is_running = self.patcher.start()

    def tearDown(self) -> None:
        self.patcher.stop()
        gc.collect()
        self.temp_dir.cleanup()

    def test_version_flag(self) -> None:
        """--version flag prints version and exits."""
        result = self.runner.invoke(app, ["--version"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("0.1.0", result.output)

    def test_help_flag(self) -> None:
        """--help displays available commands."""
        result = self.runner.invoke(app, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("audit", result.output)
        self.assertIn("fix", result.output)
        self.assertIn("watch", result.output)
        self.assertIn("rollback", result.output)

    def test_audit_command(self) -> None:
        """audit command displays audit table without modifying databases."""
        db_file = self.conv_dir / "test-c1.db"
        _create_mock_conversation(db_file, "file:///workspace/project-a", project_id=None)

        result = self.runner.invoke(
            app,
            ["--data-dir", str(self.data_dir), "--config-dir", str(self.config_dir), "audit"],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("1", result.output)
        # Verify db was untouched
        conn = sqlite3.connect(str(db_file))
        try:
            row = conn.execute("SELECT data FROM trajectory_metadata_blob WHERE id='main'").fetchone()
            self.assertNotIn(b"outside-of-project", row[0])
        finally:
            conn.close()

    def test_fix_dry_run(self) -> None:
        """fix --dry-run simulates migration without modifying files."""
        db_file = self.conv_dir / "test-c2.db"
        _create_mock_conversation(db_file, "file:///workspace/my-app", project_id=None)

        result = self.runner.invoke(
            app,
            ["--data-dir", str(self.data_dir), "--config-dir", str(self.config_dir), "fix", "--dry-run"],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertTrue("dry-run" in result.output.lower() or "simulation" in result.output.lower() or "симуляция" in result.output.lower() or "имитация" in result.output.lower())
        # Backup should not have been created in dry-run
        self.assertFalse(self.backups_dir.exists() and list(self.backups_dir.iterdir()))

    @patch("antigravity_migrator.cli.is_antigravity_running")
    @patch("antigravity_migrator.cli.get_running_pids")
    def test_fix_ide_running_prompt_decline(self, mock_pids: MagicMock, mock_running: MagicMock) -> None:
        """fix command aborts if IDE is running and user declines prompt."""
        mock_running.return_value = True
        mock_pids.return_value = [12345]

        # Decline the prompt
        result = self.runner.invoke(
            app,
            ["--data-dir", str(self.data_dir), "--config-dir", str(self.config_dir), "fix"],
            input="n\n",
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertTrue("aborted" in result.output.lower() or "отмен" in result.output.lower() or "warning" in result.output.lower() or "внимание" in result.output.lower())

    @patch("antigravity_migrator.cli.is_antigravity_running")
    def test_fix_force_when_running(self, mock_running: MagicMock) -> None:
        """fix --force proceeds immediately even if IDE is running."""
        mock_running.return_value = True
        db_file = self.conv_dir / "test-c3.db"
        _create_mock_conversation(db_file, "file:///workspace/app3", project_id=None)

        result = self.runner.invoke(
            app,
            ["--data-dir", str(self.data_dir), "--config-dir", str(self.config_dir), "fix", "--force"],
        )
        self.assertEqual(result.exit_code, 0)
        # Snapshot backup should be created
        self.assertTrue(self.backups_dir.exists())

    @patch("antigravity_migrator.cli.is_antigravity_running")
    @patch("antigravity_migrator.cli.wait_for_shutdown")
    def test_fix_watch_mode(self, mock_wait: MagicMock, mock_running: MagicMock) -> None:
        """fix --watch waits for Antigravity shutdown and then applies fixes."""
        mock_running.return_value = True
        mock_wait.return_value = True

        result = self.runner.invoke(
            app,
            ["--data-dir", str(self.data_dir), "--config-dir", str(self.config_dir), "fix", "--watch"],
        )
        self.assertEqual(result.exit_code, 0)
        mock_wait.assert_called_once()

    @patch("antigravity_migrator.cli.is_antigravity_running")
    @patch("antigravity_migrator.cli.wait_for_shutdown")
    def test_watch_command(self, mock_wait: MagicMock, mock_running: MagicMock) -> None:
        """watch command monitors IDE shutdown and automatically syncs."""
        mock_running.return_value = True
        mock_wait.return_value = True

        result = self.runner.invoke(
            app,
            ["--data-dir", str(self.data_dir), "--config-dir", str(self.config_dir), "watch"],
        )
        self.assertEqual(result.exit_code, 0)
        mock_wait.assert_called_once()

    def test_rollback_list(self) -> None:
        """rollback --list displays available snapshots."""
        snap_dir = self.backups_dir / "2026-09-29_12-00-00"
        snap_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "created_at": "2026-09-29T12:00:00",
            "source_data_dir": str(self.data_dir),
            "total_size_bytes": 1024,
            "files_count": 2,
            "files": {},
        }
        (snap_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        result = self.runner.invoke(
            app,
            ["--data-dir", str(self.data_dir), "--config-dir", str(self.config_dir), "rollback", "--list"],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("2026-09-29_12-00-00", result.output)

    def test_rollback_no_snapshots(self) -> None:
        """rollback without snapshots notifies user."""
        result = self.runner.invoke(
            app,
            ["--data-dir", str(self.data_dir), "--config-dir", str(self.config_dir), "rollback"],
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertTrue("no snapshot" in result.output.lower() or "нет" in result.output.lower() or "не найден" in result.output.lower())

    def test_rollback_specific_snapshot(self) -> None:
        """rollback restores a specific snapshot ID."""
        snap_dir = self.backups_dir / "2026-09-29_15-30-00"
        snap_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "created_at": "2026-09-29T15:30:00",
            "source_data_dir": str(self.data_dir),
            "total_size_bytes": 10,
            "files_count": 1,
            "files": {"agyhub_summaries_proto.pb": {"size": 10, "sha256": ""}},
        }
        (snap_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (snap_dir / "agyhub_summaries_proto.pb").write_bytes(b"snap-bytes")

        result = self.runner.invoke(
            app,
            [
                "--data-dir",
                str(self.data_dir),
                "--config-dir",
                str(self.config_dir),
                "rollback",
                "2026-09-29_15-30-00",
            ],
        )
        self.assertEqual(result.exit_code, 0)
        restored_pb = self.data_dir / "agyhub_summaries_proto.pb"
        self.assertTrue(restored_pb.exists())
        self.assertEqual(restored_pb.read_bytes(), b"snap-bytes")

    def test_lang_ru_flag(self) -> None:
        """--lang ru renders Russian output strings."""
        result = self.runner.invoke(
            app,
            ["--data-dir", str(self.data_dir), "--config-dir", str(self.config_dir), "--lang", "ru", "audit"],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Отчет аудита", result.output)

    def test_update_check_up_to_date(self) -> None:
        """update-check prints up to date when current version is latest."""
        with patch("antigravity_migrator.cli.check_github_update") as mock_check:
            mock_check.return_value = {
                "update_available": False,
                "current_version": "0.1.0",
                "latest_version": "0.1.0",
                "download_url": "",
                "release_notes": "",
                "published_at": "",
                "throttled": False,
                "checked": True,
                "error": None,
            }
            result = self.runner.invoke(app, ["update-check"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("0.1.0", result.output)

    def test_update_check_new_version(self) -> None:
        """update-check displays available new version and download URL."""
        with patch("antigravity_migrator.cli.check_github_update") as mock_check:
            mock_check.return_value = {
                "update_available": True,
                "current_version": "0.1.0",
                "latest_version": "0.2.0",
                "download_url": "https://github.com/Fuheshka/antigravity-chat-migrator/releases/v0.2.0",
                "release_notes": "Added update checker",
                "published_at": "2026-10-01",
                "throttled": False,
                "checked": True,
                "error": None,
            }
            result = self.runner.invoke(app, ["update-check", "--force"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("0.2.0", result.output)
            self.assertIn("https://github.com/Fuheshka/antigravity-chat-migrator/releases/v0.2.0", result.output)


if __name__ == "__main__":
    unittest.main()

