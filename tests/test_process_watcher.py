"""Unit tests for ProcessWatcher module (process detection and safe shutdown)."""

import os
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, call, patch

from antigravity_migrator.process_watcher import (
    ProcessWatcher,
    get_running_pids,
    is_antigravity_process_name,
    is_antigravity_running,
    wait_for_shutdown,
)


class TestProcessWatcher(unittest.TestCase):
    """Test suite for Antigravity process monitoring and shutdown detection."""

    def test_is_antigravity_process_name(self):
        """Test detection of Antigravity and language server process names."""
        # Positive cases (macOS, Windows, Linux)
        positive_names = [
            "Antigravity",
            "antigravity",
            "Antigravity IDE",
            "antigravity ide",
            "Antigravity Helper",
            "Antigravity Helper (Renderer)",
            "Antigravity Helper (GPU)",
            "language_server",
            "language_server_macos",
            "language_server_linux",
            "language_server_windows_x64.exe",
            "Antigravity.exe",
            "Antigravity IDE.exe",
            "language_server.exe",
        ]
        for name in positive_names:
            self.assertTrue(
                is_antigravity_process_name(name),
                f"Expected '{name}' to be recognized as Antigravity process",
            )

        # Negative cases (unrelated tools or processes)
        negative_names = [
            "antigravity-tools",
            "antigravity-chat-migrator",
            "AntigravityQuota",
            "python3",
            "pytest",
            "code",
            "electron",
            "zsh",
            "",
            None,
        ]
        for name in negative_names:
            self.assertFalse(
                is_antigravity_process_name(name),
                f"Expected '{name}' NOT to be recognized as Antigravity process",
            )

    @patch("antigravity_migrator.process_watcher.psutil")
    def test_get_running_pids_with_psutil(self, mock_psutil):
        """Test process identification using psutil when available."""
        p1 = MagicMock()
        p1.pid = 1001
        p1.name.return_value = "Antigravity"

        p2 = MagicMock()
        p2.pid = 1002
        p2.name.return_value = "language_server"

        p3 = MagicMock()
        p3.pid = 2001
        p3.name.return_value = "python3"

        # Simulating NoSuchProcess or AccessDenied on dead process
        p_dead = MagicMock()
        if hasattr(mock_psutil, "NoSuchProcess"):
            p_dead.name.side_effect = mock_psutil.NoSuchProcess(pid=9999)
        else:
            p_dead.name.side_effect = Exception("NoSuchProcess")

        mock_psutil.process_iter.return_value = [p1, p2, p3, p_dead]

        pids = get_running_pids()
        self.assertEqual(sorted(pids), [1001, 1002])

    @patch("antigravity_migrator.process_watcher.psutil", None)
    @patch("platform.system", return_value="Darwin")
    @patch("subprocess.run")
    def test_get_running_pids_fallback_darwin(self, mock_run, mock_platform):
        """Test fallback process detection on macOS via ps -A -o pid=,comm=."""
        mock_output = (
            "  101 /Applications/Antigravity.app/Contents/MacOS/Antigravity\n"
            "  102 /Applications/Antigravity.app/Contents/Resources/bin/language_server\n"
            "  201 /usr/local/bin/python3\n"
            "  301 /Applications/AntigravityQuota.app/Contents/MacOS/AntigravityQuota\n"
        )
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_output)

        pids = get_running_pids()
        self.assertEqual(sorted(pids), [101, 102])
        mock_run.assert_called_once()

    @patch("antigravity_migrator.process_watcher.psutil", None)
    @patch("platform.system", return_value="Windows")
    @patch("subprocess.run")
    def test_get_running_pids_fallback_windows(self, mock_run, mock_platform):
        """Test fallback process detection on Windows via tasklist CSV."""
        mock_output = (
            '"Antigravity.exe","4001","Console","1","150,000 K"\r\n'
            '"language_server.exe","4002","Console","1","80,000 K"\r\n'
            '"explorer.exe","1000","Console","1","50,000 K"\r\n'
        )
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_output)

        pids = get_running_pids()
        self.assertEqual(sorted(pids), [4001, 4002])
        mock_run.assert_called_once()

    @patch("antigravity_migrator.process_watcher.get_running_pids")
    def test_is_antigravity_running(self, mock_get_pids):
        """Test boolean check for process presence."""
        mock_get_pids.return_value = [1234]
        self.assertTrue(is_antigravity_running())

        mock_get_pids.return_value = []
        self.assertFalse(is_antigravity_running())

    @patch("antigravity_migrator.process_watcher.get_running_pids")
    def test_wait_for_shutdown_already_stopped(self, mock_get_pids):
        """Test wait_for_shutdown when no processes are running initially."""
        mock_get_pids.return_value = []
        with patch("time.sleep") as mock_sleep:
            res = wait_for_shutdown(timeout_seconds=5.0, poll_interval=0.1)
            self.assertTrue(res)
            mock_sleep.assert_not_called()

    @patch("antigravity_migrator.process_watcher.get_running_pids")
    def test_wait_for_shutdown_terminates_in_time(self, mock_get_pids):
        """Test wait_for_shutdown when process terminates after polling."""
        # 1st call: running, 2nd call: stopped
        mock_get_pids.side_effect = [[101], []]

        with patch("time.sleep") as mock_sleep:
            res = wait_for_shutdown(timeout_seconds=5.0, poll_interval=0.1)
            self.assertTrue(res)
            # Should have slept poll_interval (0.1) and safety_pause (1.0)
            mock_sleep.assert_has_calls([call(0.1), call(1.0)])

    @patch("antigravity_migrator.process_watcher.get_running_pids")
    def test_wait_for_shutdown_timeout(self, mock_get_pids):
        """Test wait_for_shutdown returning False when timeout expires."""
        mock_get_pids.return_value = [101]

        with patch("time.sleep"):
            res = wait_for_shutdown(timeout_seconds=0.01, poll_interval=0.005)
            self.assertFalse(res)

    @patch("antigravity_migrator.process_watcher.get_running_pids")
    def test_process_watcher_class(self, mock_get_pids):
        """Test ProcessWatcher class methods."""
        watcher = ProcessWatcher()
        mock_get_pids.return_value = [555]

        self.assertTrue(watcher.is_running())
        self.assertEqual(watcher.get_pids(), [555])

        mock_get_pids.return_value = []
        self.assertFalse(watcher.is_running())

    @patch("antigravity_migrator.process_watcher.wait_for_shutdown")
    def test_process_watcher_wait_delegation(self, mock_wait):
        """Test ProcessWatcher.wait_for_shutdown delegates to module function."""
        watcher = ProcessWatcher(safety_pause=2.5)
        mock_wait.return_value = True

        res = watcher.wait_for_shutdown(timeout_seconds=30.0, poll_interval=1.0)
        self.assertTrue(res)
        mock_wait.assert_called_once_with(
            timeout_seconds=30.0,
            poll_interval=1.0,
            safety_pause=2.5,
        )

    def test_package_exports(self):
        """Test that all required symbols are exported from root package."""
        import antigravity_migrator

        self.assertTrue(hasattr(antigravity_migrator, "ProcessWatcher"))
        self.assertTrue(hasattr(antigravity_migrator, "is_antigravity_running"))
        self.assertTrue(hasattr(antigravity_migrator, "get_running_pids"))
        self.assertTrue(hasattr(antigravity_migrator, "wait_for_shutdown"))
        self.assertTrue(hasattr(antigravity_migrator, "is_antigravity_process_name"))


if __name__ == "__main__":
    unittest.main()
