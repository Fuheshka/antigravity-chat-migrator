"""Tests for Antigravity Chat Migrator frontend assets (HTML, CSS, JavaScript).

Validates:
1. Presence of index.html, style.css, app.js in the package distribution.
2. Syntax validity of HTML, CSS, and JavaScript.
3. Presence of all critical UI elements: ASCII art banner, metric containers,
   conversations data table, action buttons, search & filters, modal, and toast container.
4. Completeness and consistency of bilingual internationalization (RU & EN).
5. Adherence to sentence case rules in Russian typography.
"""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
from typing import Dict, List, Set

import pytest

from antigravity_migrator.gui import get_gui_asset_dir, get_gui_index_path


class _HTMLValidator(HTMLParser):
    """HTML parser to validate structure and collect element tags and attributes."""

    def __init__(self) -> None:
        super().__init__()
        self.tags: List[str] = []
        self.ids: Set[str] = set()
        self.classes: Set[str] = set()
        self.i18n_keys: Set[str] = set()
        self.i18n_placeholder_keys: Set[str] = set()
        self.filter_values: Set[str] = set()
        self.scripts: List[str] = []
        self.stylesheets: List[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        attr_dict = {k: (v or "") for k, v in attrs}

        if "id" in attr_dict:
            self.ids.add(attr_dict["id"])

        if "class" in attr_dict:
            for cls in attr_dict["class"].split():
                self.classes.add(cls)

        if "data-i18n" in attr_dict:
            self.i18n_keys.add(attr_dict["data-i18n"])

        if "data-i18n-placeholder" in attr_dict:
            self.i18n_placeholder_keys.add(attr_dict["data-i18n-placeholder"])

        if "data-filter" in attr_dict:
            self.filter_values.add(attr_dict["data-filter"])

        if tag == "link" and attr_dict.get("rel") == "stylesheet":
            self.stylesheets.append(attr_dict.get("href", ""))

        if tag == "script" and attr_dict.get("src"):
            self.scripts.append(attr_dict.get("src", ""))


@pytest.fixture(scope="module")
def gui_dir() -> Path:
    """Fixture providing path to GUI assets directory."""
    return get_gui_asset_dir()


@pytest.fixture(scope="module")
def html_content(gui_dir: Path) -> str:
    """Fixture reading index.html text."""
    path = gui_dir / "index.html"
    assert path.is_file(), f"index.html missing at {path}"
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def css_content(gui_dir: Path) -> str:
    """Fixture reading style.css text."""
    path = gui_dir / "style.css"
    assert path.is_file(), f"style.css missing at {path}"
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def js_content(gui_dir: Path) -> str:
    """Fixture reading app.js text."""
    path = gui_dir / "app.js"
    assert path.is_file(), f"app.js missing at {path}"
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def html_parsed(html_content: str) -> _HTMLValidator:
    """Fixture providing parsed HTML elements and attributes."""
    parser = _HTMLValidator()
    parser.feed(html_content)
    return parser


# ============================================================================
# 1. Package Distribution & Asset Presence
# ============================================================================

def test_gui_assets_exist(gui_dir: Path):
    """Verify that all core frontend assets exist and are non-empty."""
    assert gui_dir.is_dir(), f"GUI directory does not exist: {gui_dir}"

    index_html = gui_dir / "index.html"
    style_css = gui_dir / "style.css"
    app_js = gui_dir / "app.js"

    assert index_html.is_file()
    assert index_html.stat().st_size > 500, "index.html is unexpectedly small"

    assert style_css.is_file()
    assert style_css.stat().st_size > 1000, "style.css is unexpectedly small"

    assert app_js.is_file()
    assert app_js.stat().st_size > 1000, "app.js is unexpectedly small"


def test_get_gui_index_path_helper():
    """Verify get_gui_index_path returns an existing index.html."""
    idx = get_gui_index_path()
    assert idx.is_file()
    assert idx.name == "index.html"


# ============================================================================
# 2. HTML Syntax and Document Structure
# ============================================================================

def test_html_document_structure(html_content: str, html_parsed: _HTMLValidator):
    """Verify standard HTML5 document structure and external links."""
    assert "<!DOCTYPE html>" in html_content or "<!doctype html>" in html_content
    assert "html" in html_parsed.tags
    assert "head" in html_parsed.tags
    assert "body" in html_parsed.tags

    # Verify stylesheet link
    assert "style.css" in html_parsed.stylesheets

    # Verify script link
    assert "app.js" in html_parsed.scripts


# ============================================================================
# 3. ASCII Art Banner Element
# ============================================================================

def test_html_ascii_banner(html_parsed: _HTMLValidator, html_content: str):
    """Verify presence of ASCII art banner card and terminal styling elements."""
    assert "asciiBanner" in html_parsed.ids
    assert "ascii-art" in html_parsed.classes
    assert "banner-card" in html_parsed.classes
    assert "terminal-decorations" in html_parsed.classes

    # Terminal window controls
    assert "dot-red" in html_parsed.classes
    assert "dot-yellow" in html_parsed.classes
    assert "dot-green" in html_parsed.classes

    # Text content of ASCII art banner
    assert "antigravity-core" in html_content


# ============================================================================
# 4. Metric Containers & Indicators
# ============================================================================

def test_html_metric_cards(html_parsed: _HTMLValidator):
    """Verify all 5 metric cards and corresponding value containers exist."""
    required_cards = {
        "cardTotal",
        "cardBound",
        "cardOutside",
        "cardMissing",
        "cardUnregistered",
    }
    required_values = {
        "valTotal",
        "valBound",
        "valOutside",
        "valMissing",
        "valUnregistered",
    }

    assert required_cards.issubset(html_parsed.ids), f"Missing cards: {required_cards - html_parsed.ids}"
    assert required_values.issubset(html_parsed.ids), f"Missing values: {required_values - html_parsed.ids}"
    assert "metrics-grid" in html_parsed.classes
    assert "metric-card" in html_parsed.classes


# ============================================================================
# 5. Action Buttons & Navigation Controls
# ============================================================================

def test_html_action_buttons_and_controls(html_parsed: _HTMLValidator):
    """Verify primary action buttons, process status badge, and language switch."""
    # Main action buttons
    assert "btnScan" in html_parsed.ids
    assert "btnDryRun" in html_parsed.ids
    assert "btnFix" in html_parsed.ids
    assert "btnBackups" in html_parsed.ids

    # Search & filters
    assert "searchInput" in html_parsed.ids
    assert "btnClearSearch" in html_parsed.ids
    assert {"all", "outside", "missing", "unregistered"}.issubset(html_parsed.filter_values)

    # Process status badge
    assert "processBadge" in html_parsed.ids
    assert "processBadgeText" in html_parsed.ids
    assert "badge-status" in html_parsed.classes

    # Language toggle
    assert "langToggle" in html_parsed.ids
    assert "langCurrent" in html_parsed.ids


# ============================================================================
# 6. Conversations Data Table
# ============================================================================

def test_html_conversations_table(html_parsed: _HTMLValidator):
    """Verify data table, header elements, table body, and empty state."""
    assert "conversationsTable" in html_parsed.ids
    assert "tableBody" in html_parsed.ids
    assert "data-table" in html_parsed.classes
    assert "emptyState" in html_parsed.ids
    assert "tableLoader" in html_parsed.ids

    # Required table header i18n keys
    table_col_keys = {"colStatus", "colTitle", "colWorkspace", "colProject", "colId"}
    assert table_col_keys.issubset(html_parsed.i18n_keys)


# ============================================================================
# 7. Backup Modal and Toast Notifications
# ============================================================================

def test_html_modal_and_toast(html_parsed: _HTMLValidator):
    """Verify backup modal dialog and toast notification elements."""
    assert "backupModal" in html_parsed.ids
    assert "modalTitle" in html_parsed.ids
    assert "btnCloseModal" in html_parsed.ids
    assert "modalColdDiskWarn" in html_parsed.ids
    assert "backupList" in html_parsed.ids
    assert "emptyBackups" in html_parsed.ids
    assert "toastContainer" in html_parsed.ids


# ============================================================================
# 8. CSS Syntax & Design System Rules
# ============================================================================

def test_css_syntax_and_theming(css_content: str):
    """Verify CSS syntax integrity (balanced braces) and core theme tokens."""
    # Balanced braces
    open_braces = css_content.count("{")
    close_braces = css_content.count("}")
    assert open_braces == close_braces, f"Mismatched braces in CSS: {open_braces} != {close_braces}"

    # Balanced comments
    open_comments = css_content.count("/*")
    close_comments = css_content.count("*/")
    assert open_comments == close_comments, "Mismatched comment tokens in CSS"

    # Core theme classes
    for selector in [
        ".ascii-art",
        ".metrics-grid",
        ".metric-card",
        ".data-table",
        ".badge-status",
        ".modal-card",
        ".toast-container",
    ]:
        assert selector in css_content, f"Missing CSS selector: {selector}"


# ============================================================================
# 9. JavaScript Syntax, Bridge API Calls & i18n Consistency
# ============================================================================

def _extract_translations_from_js(js_content: str) -> Dict[str, Dict[str, str]]:
    """Helper to extract TRANSLATIONS ru and en dictionaries from app.js."""
    ru_dict: Dict[str, str] = {}
    en_dict: Dict[str, str] = {}

    m_ru = re.search(r"ru:\s*\{(.*?)\n\s*\},\s*\n\s*en:", js_content, re.DOTALL)
    m_en = re.search(r"en:\s*\{(.*?)\n\s*\}\s*\n\s*\};", js_content, re.DOTALL)

    def _parse_body(body: str) -> Dict[str, str]:
        parsed = {}
        for line in body.splitlines():
            line = line.strip()
            kv = re.match(r"(\w+):\s*['\"](.*)['\"],?$", line)
            if kv:
                parsed[kv.group(1)] = kv.group(2)
        return parsed

    if m_ru:
        ru_dict = _parse_body(m_ru.group(1))
    if m_en:
        en_dict = _parse_body(m_en.group(1))

    return {"ru": ru_dict, "en": en_dict}


def test_js_syntax_integrity(js_content: str):
    """Verify balanced parentheses, brackets, and braces in JavaScript controller."""
    # Balanced braces
    assert js_content.count("{") == js_content.count("}")
    # Balanced brackets
    assert js_content.count("[") == js_content.count("]")
    # Balanced parentheses
    assert js_content.count("(") == js_content.count(")")


def test_js_calls_all_bridge_methods(js_content: str):
    """Verify app.js invokes all 6 methods of the GuiBridgeApi contract."""
    bridge_methods = [
        "get_system_info",
        "get_process_status",
        "run_audit",
        "run_fix",
        "list_backups",
        "restore_backup",
    ]
    for method in bridge_methods:
        assert method in js_content, f"Bridge method '{method}' is not referenced in app.js"


def test_i18n_keys_completeness_and_parity(html_parsed: _HTMLValidator, js_content: str):
    """Verify all data-i18n attributes have non-empty translations in both RU and EN."""
    translations = _extract_translations_from_js(js_content)
    ru_keys = set(translations["ru"].keys())
    en_keys = set(translations["en"].keys())

    all_html_keys = html_parsed.i18n_keys | html_parsed.i18n_placeholder_keys

    assert len(ru_keys) > 30
    assert len(en_keys) > 30

    # Every key in HTML must be present in ru and en
    for key in all_html_keys:
        assert key in ru_keys, f"HTML i18n key '{key}' is missing in RU translations"
        assert key in en_keys, f"HTML i18n key '{key}' is missing in EN translations"
        assert len(translations["ru"][key].strip()) > 0
        assert len(translations["en"][key].strip()) > 0


def test_russian_typography_no_title_case(js_content: str):
    """Verify that Russian UI translations adhere to sentence case (no English Title Case)."""
    translations = _extract_translations_from_js(js_content)
    ru_dict = translations["ru"]

    forbidden_title_cases = [
        "Всего Диалогов",
        "Статус Процесса",
        "В Проектах",
        "Без Аннотаций",
        "Вне Реестра",
        "Откат Из Бэкапа",
        "Название Диалога",
        "Рабочая Папка",
        "Резервные Снимки",
    ]

    for key, text in ru_dict.items():
        for forbidden in forbidden_title_cases:
            assert forbidden not in text, f"Key '{key}' violates Russian sentence case rule: '{text}' contains '{forbidden}'"
