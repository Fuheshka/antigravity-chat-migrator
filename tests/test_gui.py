"""Unit and integration tests for Antigravity Chat Migrator GUI launcher (gui.py) and CLI routing."""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from antigravity_migrator.cli import app
from antigravity_migrator.gui import (
    get_gui_asset_dir,
    get_gui_index_path,
    launch_gui,
)
from antigravity_migrator.gui_api import GuiBridgeApi


class TestGuiLauncher(unittest.TestCase):
    """Test suite for GUI assets resolution and pywebview window initialization."""

    def test_get_gui_asset_dir_default(self) -> None:
        """Asset dir resolves to local package directory with required frontend files."""
        asset_dir = get_gui_asset_dir()
        self.assertTrue(asset_dir.exists())
        self.assertTrue(asset_dir.is_dir())
        self.assertTrue((asset_dir / "index.html").is_file())
        self.assertTrue((asset_dir / "style.css").is_file())
        self.assertTrue((asset_dir / "app.js").is_file())

    def test_get_gui_asset_dir_meipass(self) -> None:
        """Asset dir prioritizes PyInstaller _MEIPASS bundle when frozen."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            bundle_dir = Path(tmp_dir)
            fake_gui = bundle_dir / "antigravity_migrator" / "gui"
            fake_gui.mkdir(parents=True, exist_ok=True)
            (fake_gui / "index.html").write_text("<html></html>", encoding="utf-8")

            with patch.object(sys, "_MEIPASS", str(bundle_dir), create=True):
                resolved = get_gui_asset_dir()
                self.assertEqual(resolved, fake_gui)

    def test_get_gui_asset_dir_not_found(self) -> None:
        """Raises FileNotFoundError when frontend asset directory cannot be found."""
        with patch("pathlib.Path.exists", return_value=False):
            with self.assertRaises(FileNotFoundError):
                get_gui_asset_dir()

    def test_get_gui_index_path(self) -> None:
        """Resolves existing path to index.html."""
        index_path = get_gui_index_path()
        self.assertTrue(index_path.is_file())
        self.assertEqual(index_path.name, "index.html")

    @patch("antigravity_migrator.gui.webview")
    def test_launch_gui_default_parameters(self, mock_webview: MagicMock) -> None:
        """launch_gui creates window with default dimensions, dark theme, and centered position."""
        mock_window = MagicMock()
        mock_webview.create_window.return_value = mock_window

        win = launch_gui(start_loop=False)

        self.assertEqual(win, mock_window)
        mock_webview.create_window.assert_called_once()
        _, kwargs = mock_webview.create_window.call_args

        self.assertEqual(kwargs.get("title"), "Antigravity Chat Migrator")
        self.assertEqual(kwargs.get("width"), 1024)
        self.assertEqual(kwargs.get("height"), 720)
        self.assertEqual(kwargs.get("min_size"), (800, 560))
        self.assertEqual(kwargs.get("background_color"), "#0d1117")
        self.assertTrue(kwargs.get("resizable"))
        self.assertIsNone(kwargs.get("x"))
        self.assertIsNone(kwargs.get("y"))
        self.assertIsInstance(kwargs.get("js_api"), GuiBridgeApi)
        self.assertTrue(str(kwargs.get("url")).endswith("index.html"))
        mock_webview.start.assert_not_called()

    @patch("antigravity_migrator.gui.webview")
    def test_launch_gui_custom_parameters_and_start(self, mock_webview: MagicMock) -> None:
        """launch_gui respects custom title, size, debug mode, and custom API bridge."""
        mock_window = MagicMock()
        mock_webview.create_window.return_value = mock_window
        custom_api = MagicMock(spec=GuiBridgeApi)

        win = launch_gui(
            title="Custom Title",
            width=1280,
            height=800,
            debug=True,
            api=custom_api,
            start_loop=True,
        )

        self.assertEqual(win, mock_window)
        _, kwargs = mock_webview.create_window.call_args
        self.assertEqual(kwargs.get("title"), "Custom Title")
        self.assertEqual(kwargs.get("width"), 1280)
        self.assertEqual(kwargs.get("height"), 800)
        self.assertEqual(kwargs.get("js_api"), custom_api)
        mock_webview.start.assert_called_once_with(debug=True)

    def test_launch_gui_missing_webview_dependency(self) -> None:
        """Raises RuntimeError with actionable message when pywebview is not installed."""
        with patch("antigravity_migrator.gui.webview", None):
            with self.assertRaises(RuntimeError) as ctx:
                launch_gui()
            self.assertIn("pywebview is required", str(ctx.exception))


class TestCliGuiRouting(unittest.TestCase):
    """Test suite for CLI routing: default GUI vs --cli/--tui vs subcommands."""

    def setUp(self) -> None:
        self.runner = CliRunner()

    @patch("antigravity_migrator.gui.launch_gui")
    def test_cli_default_launches_gui(self, mock_launch_gui: MagicMock) -> None:
        """Calling agy-migrator without subcommands launches GUI by default."""
        result = self.runner.invoke(app, [])
        self.assertEqual(result.exit_code, 0)
        mock_launch_gui.assert_called_once_with(debug=False)

    @patch("antigravity_migrator.gui.launch_gui")
    def test_cli_default_debug_flag_passed_to_gui(self, mock_launch_gui: MagicMock) -> None:
        """Calling agy-migrator --debug passes debug=True to launch_gui."""
        result = self.runner.invoke(app, ["--debug"])
        self.assertEqual(result.exit_code, 0)
        mock_launch_gui.assert_called_once_with(debug=True)

    @patch("antigravity_migrator.gui.launch_gui")
    def test_cli_flag_forces_terminal_mode(self, mock_launch_gui: MagicMock) -> None:
        """Calling agy-migrator --cli stays in terminal mode and does not launch GUI."""
        result = self.runner.invoke(app, ["--cli"])
        self.assertEqual(result.exit_code, 0)
        mock_launch_gui.assert_not_called()
        self.assertIn("Antigravity Chat Migrator", result.output)
        self.assertIn("audit", result.output)
        self.assertIn("fix", result.output)

    @patch("antigravity_migrator.gui.launch_gui")
    def test_tui_flag_forces_terminal_mode(self, mock_launch_gui: MagicMock) -> None:
        """Calling agy-migrator --tui stays in terminal mode and does not launch GUI."""
        result = self.runner.invoke(app, ["--tui", "--lang", "ru"])
        self.assertEqual(result.exit_code, 0)
        mock_launch_gui.assert_not_called()
        self.assertIn("Восстановление чатов", result.output)
        self.assertIn("audit", result.output)

    @patch("antigravity_migrator.gui.launch_gui")
    @patch("antigravity_migrator.cli.is_antigravity_running", return_value=False)
    def test_subcommand_audit_does_not_launch_gui(
        self, mock_is_running: MagicMock, mock_launch_gui: MagicMock
    ) -> None:
        """Calling agy-migrator audit executes the terminal command and does not launch GUI."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = Path(tmp_dir) / "gemini" / "antigravity"
            data_dir.mkdir(parents=True, exist_ok=True)
            result = self.runner.invoke(app, ["--lang", "en", "--data-dir", str(data_dir), "audit"])
            self.assertEqual(result.exit_code, 0)
            mock_launch_gui.assert_not_called()
            self.assertIn("Audit Report", result.output)


if __name__ == "__main__":
    unittest.main()
