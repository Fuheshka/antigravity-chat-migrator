"""Tests for i18n localization and UI rendering components."""

from __future__ import annotations

import io
import os
import unittest
from unittest.mock import patch

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress
from rich.table import Table

from antigravity_migrator.service import AuditReport
from antigravity_migrator.i18n import (
    MESSAGES,
    detect_locale,
    get_current_locale,
    normalize_locale,
    set_current_locale,
    t,
)
from antigravity_migrator.ui_renderer import (
    render_audit_table,
    render_banner,
    render_sync_progress,
    render_warning_cold_disk,
)


class TestI18nLocalization(unittest.TestCase):
    """Test suite for internationalization and locale resolution."""

    def setUp(self) -> None:
        self.original_locale = get_current_locale()

    def tearDown(self) -> None:
        set_current_locale(self.original_locale)

    def test_messages_dictionary_completeness(self) -> None:
        """Verify that RU and EN dictionaries are 100% mirrored and non-empty."""
        self.assertIn("en", MESSAGES)
        self.assertIn("ru", MESSAGES)

        en_keys = set(MESSAGES["en"].keys())
        ru_keys = set(MESSAGES["ru"].keys())

        missing_in_ru = en_keys - ru_keys
        missing_in_en = ru_keys - en_keys

        self.assertEqual(
            missing_in_ru,
            set(),
            f"Keys missing in RU dictionary: {missing_in_ru}",
        )
        self.assertEqual(
            missing_in_en,
            set(),
            f"Keys missing in EN dictionary: {missing_in_en}",
        )

        for lang in ("en", "ru"):
            for key, val in MESSAGES[lang].items():
                self.assertIsInstance(val, str, f"Value for {lang}:{key} must be str")
                self.assertTrue(val.strip(), f"Value for {lang}:{key} cannot be empty")

    def test_normalize_locale(self) -> None:
        """Test locale string normalization."""
        self.assertEqual(normalize_locale("ru"), "ru")
        self.assertEqual(normalize_locale("RU"), "ru")
        self.assertEqual(normalize_locale("ru_RU"), "ru")
        self.assertEqual(normalize_locale("ru_RU.UTF-8"), "ru")
        self.assertEqual(normalize_locale("russian"), "ru")

        self.assertEqual(normalize_locale("en"), "en")
        self.assertEqual(normalize_locale("en_US"), "en")
        self.assertEqual(normalize_locale("en_GB.UTF-8"), "en")
        self.assertEqual(normalize_locale("english"), "en")

        self.assertEqual(normalize_locale("de_DE"), "en")
        self.assertEqual(normalize_locale(""), "en")
        self.assertEqual(normalize_locale(None), "en")

    def test_detect_locale_via_env_lang(self) -> None:
        """Test detection via LANG environment variable."""
        with patch.dict(os.environ, {"LANG": "ru_RU.UTF-8"}):
            self.assertEqual(detect_locale(), "ru")

        with patch.dict(os.environ, {"LANG": "en_US.UTF-8"}):
            self.assertEqual(detect_locale(), "en")

    def test_detect_locale_via_getdefaultlocale(self) -> None:
        """Test detection via locale.getdefaultlocale fallback."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("locale.getdefaultlocale", return_value=("ru_RU", "UTF-8")):
                self.assertEqual(detect_locale(), "ru")

            with patch("locale.getdefaultlocale", return_value=("en_US", "UTF-8")):
                self.assertEqual(detect_locale(), "en")

            with patch("locale.getdefaultlocale", return_value=(None, None)):
                self.assertEqual(detect_locale(), "en")

    def test_t_function_translation(self) -> None:
        """Test translation lookups with explicit language."""
        text_en = t("banner_subtitle", lang="en")
        text_ru = t("banner_subtitle", lang="ru")

        self.assertIsInstance(text_en, str)
        self.assertIsInstance(text_ru, str)
        self.assertNotEqual(text_en, text_ru)

        # Fallback to key if unknown
        self.assertEqual(t("non_existing_key_xyz", lang="en"), "non_existing_key_xyz")

    def test_t_function_kwargs_formatting(self) -> None:
        """Test string formatting interpolation in t()."""
        formatted_en = t("warning_active_pids", lang="en", pids="1234, 5678")
        self.assertIn("1234, 5678", formatted_en)

        formatted_ru = t("warning_active_pids", lang="ru", pids="1234, 5678")
        self.assertIn("1234, 5678", formatted_ru)

    def test_set_current_locale_behavior(self) -> None:
        """Test setting global locale affects t() when lang=None."""
        set_current_locale("ru")
        self.assertEqual(get_current_locale(), "ru")
        self.assertEqual(t("table_status_ok"), MESSAGES["ru"]["table_status_ok"])

        set_current_locale("en")
        self.assertEqual(get_current_locale(), "en")
        self.assertEqual(t("table_status_ok"), MESSAGES["en"]["table_status_ok"])


class TestUiRenderer(unittest.TestCase):
    """Test suite for Rich UI rendering components."""

    def setUp(self) -> None:
        self.buffer = io.StringIO()
        self.console = Console(file=self.buffer, force_terminal=True, width=100)

    def test_render_banner(self) -> None:
        """Test banner generation and styling."""
        panel = render_banner(console=self.console, lang="en")
        self.assertIsInstance(panel, Panel)
        output = self.buffer.getvalue()
        self.assertIn("Antigravity", output)
        self.assertIn("0.1.0", output)

    def test_render_audit_table_clean(self) -> None:
        """Test audit table rendering with all clean metrics."""
        report = AuditReport(
            total_conversations=15,
            bound_to_projects=15,
            outside_of_project=0,
            missing_annotations=0,
            unregistered_workspaces=[],
        )
        table = render_audit_table(report, console=self.console, lang="en")
        self.assertIsInstance(table, Table)
        output = self.buffer.getvalue()
        self.assertIn("15", output)
        self.assertIn("OK", output)

    def test_render_audit_table_with_issues(self) -> None:
        """Test audit table rendering when issues are detected."""
        report = AuditReport(
            total_conversations=20,
            bound_to_projects=12,
            outside_of_project=8,
            missing_annotations=5,
            unregistered_workspaces=["/path/to/project1", "/path/to/project2"],
        )
        table = render_audit_table(report, console=self.console, lang="ru")
        self.assertIsInstance(table, Table)
        output = self.buffer.getvalue()
        self.assertIn("20", output)
        self.assertIn("8", output)
        self.assertIn("5", output)

    def test_render_warning_cold_disk(self) -> None:
        """Test cold disk warning panel rendering with and without PIDs."""
        panel = render_warning_cold_disk(console=self.console, lang="en", pids=[101, 102])
        self.assertIsInstance(panel, Panel)
        output = self.buffer.getvalue()
        self.assertIn("101, 102", output)

    def test_render_warning_cold_disk_no_pids(self) -> None:
        """Test cold disk warning panel rendering with no PIDs."""
        panel = render_warning_cold_disk(console=self.console, lang="ru")
        self.assertIsInstance(panel, Panel)
        output = self.buffer.getvalue()
        self.assertIn("Antigravity", output)

    def test_render_sync_progress(self) -> None:
        """Test sync progress bar constructor."""
        progress = render_sync_progress(console=self.console, lang="en")
        self.assertIsInstance(progress, Progress)
        task_id = progress.add_task("Testing step", total=100)
        progress.update(task_id, advance=50)
        self.assertEqual(progress.tasks[0].completed, 50)


if __name__ == "__main__":
    unittest.main()
