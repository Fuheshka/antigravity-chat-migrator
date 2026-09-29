"""Bilingual localization module (English & Russian) for Antigravity Chat Migrator."""

from __future__ import annotations

import os
from typing import Any, Optional
import warnings

__all__ = [
    "MESSAGES",
    "normalize_locale",
    "detect_locale",
    "get_current_locale",
    "set_current_locale",
    "t",
]

# Bilingual translation dictionaries
# Notice: Sentence case for Russian strings according to typography guidelines
MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "banner_title": "ANTIGRAVITY CHAT MIGRATOR",
        "banner_subtitle": "Chat Repair, Workspace Sync & History Preserver",
        "banner_version": "Version {version}",
        "banner_rule_cold_disk": "Cold-disk rule: close Antigravity IDE before writing",
        "table_title": "Chat & Workspace Audit Report",
        "table_col_metric": "Metric",
        "table_col_count": "Count",
        "table_col_status": "Status",
        "table_metric_total": "Total conversations scanned",
        "table_metric_bound": "Bound to projects",
        "table_metric_outside": "Outside of project (unlinked)",
        "table_metric_missing_anno": "Missing annotations (.pbtxt)",
        "table_metric_unregistered": "Unregistered workspaces",
        "table_status_ok": "OK",
        "table_status_warning": "Needs Attention",
        "table_status_fixed": "Will be Fixed",
        "table_status_ready": "Ready",
        "warning_cold_disk_title": "CRITICAL: Antigravity IDE is Active",
        "warning_cold_disk_body": (
            "Writing to active SQLite databases and Protobuf caches while Antigravity is running "
            "can cause database locks, corruption or loss of recent conversations."
        ),
        "warning_cold_disk_advice": (
            "Please close Antigravity IDE and Language Server completely before proceeding."
        ),
        "warning_active_pids": "Detected active process PIDs: {pids}",
        "progress_title": "Synchronizing Antigravity data...",
        "progress_step_backup": "Creating safety backup snapshot...",
        "progress_step_workspaces": "Resolving workspaces and projects...",
        "progress_step_conversations": "Updating conversation metadata...",
        "progress_step_annotations": "Generating missing annotations...",
        "progress_step_proto_cache": "Patching language server summary cache...",
        "progress_step_summary_db": "Updating summary database records...",
        "progress_done": "Synchronization finished successfully.",
    },
    "ru": {
        "banner_title": "ANTIGRAVITY CHAT MIGRATOR",
        "banner_subtitle": "Восстановление чатов, синхронизация рабочих пространств и истории",
        "banner_version": "Версия {version}",
        "banner_rule_cold_disk": "Правило холодной записи: закройте Antigravity IDE перед записью",
        "table_title": "Отчет аудита чатов и рабочих пространств",
        "table_col_metric": "Метрика",
        "table_col_count": "Количество",
        "table_col_status": "Статус",
        "table_metric_total": "Всего просканировано диалогов",
        "table_metric_bound": "Привязано к проектам",
        "table_metric_outside": "Вне проекта (без привязки)",
        "table_metric_missing_anno": "Отсутствуют аннотации (.pbtxt)",
        "table_metric_unregistered": "Незарегистрированные рабочие пространства",
        "table_status_ok": "В норме",
        "table_status_warning": "Требует внимания",
        "table_status_fixed": "Будет исправлено",
        "table_status_ready": "Готово к работе",
        "warning_cold_disk_title": "ВНИМАНИЕ: Antigravity IDE активна",
        "warning_cold_disk_body": (
            "Запись в активные базы данных SQLite и Protobuf кэши при работающей Antigravity "
            "может привести к блокировкам баз данных, повреждению файлов или потере свежих чатов."
        ),
        "warning_cold_disk_advice": (
            "Пожалуйста, полностью закройте Antigravity IDE и Language Server перед выполнением операции."
        ),
        "warning_active_pids": "Обнаружены активные PID процессов: {pids}",
        "progress_title": "Синхронизация данных Antigravity...",
        "progress_step_backup": "Создание резервной копии...",
        "progress_step_workspaces": "Сопоставление рабочих пространств и проектов...",
        "progress_step_conversations": "Обновление метаданных диалогов...",
        "progress_step_annotations": "Генерация недостающих аннотаций...",
        "progress_step_proto_cache": "Патчинг кэша сводок языкового сервера...",
        "progress_step_summary_db": "Обновление записей базы данных сводок...",
        "progress_done": "Синхронизация успешно завершена.",
    },
}

_CURRENT_LOCALE: Optional[str] = None


def normalize_locale(lang: Optional[str]) -> str:
    """Normalize language code to supported locale ('en' or 'ru').

    Args:
        lang: Language string (e.g. 'ru', 'RU', 'ru_RU.UTF-8', 'en_US', 'russian').

    Returns:
        'ru' if Russian is identified, else 'en'.
    """
    if not lang:
        return "en"
    clean = str(lang).strip().lower()
    if clean.startswith("ru") or "russian" in clean:
        return "ru"
    return "en"


def detect_locale() -> str:
    """Detect operating system language or environment locale.

    Checks:
    1. Environment variables LANG, LC_ALL, LC_MESSAGES.
    2. locale.getdefaultlocale() fallback.
    3. locale.getlocale() fallback.
    4. Defaults to 'en'.

    Returns:
        'ru' or 'en'.
    """
    for env_var in ("LANG", "LC_ALL", "LC_MESSAGES"):
        val = os.environ.get(env_var)
        if val:
            return normalize_locale(val)

    try:
        import locale

        if hasattr(locale, "getdefaultlocale"):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                default_loc = locale.getdefaultlocale()
            if default_loc and default_loc[0]:
                return normalize_locale(default_loc[0])
    except Exception:
        pass

    try:
        import locale

        loc = locale.getlocale()
        if loc and loc[0]:
            return normalize_locale(loc[0])
    except Exception:
        pass

    return "en"


def get_current_locale() -> str:
    """Return currently active locale ('en' or 'ru')."""
    global _CURRENT_LOCALE
    if _CURRENT_LOCALE is None:
        _CURRENT_LOCALE = detect_locale()
    return _CURRENT_LOCALE


def set_current_locale(lang: Optional[str]) -> None:
    """Explicitly set current locale ('en', 'ru') or None to re-detect."""
    global _CURRENT_LOCALE
    if lang is None:
        _CURRENT_LOCALE = None
    else:
        _CURRENT_LOCALE = normalize_locale(lang)


def t(key: str, lang: Optional[str] = None, **kwargs: Any) -> str:
    """Translate message key for given or active locale with optional keyword interpolation.

    Args:
        key: Translation key.
        lang: Optional explicit locale ('ru' or 'en'). If omitted, uses active locale.
        **kwargs: Values to format into translated message.

    Returns:
        Formatted translated string, or key if translation is not found.
    """
    target_lang = normalize_locale(lang) if lang else get_current_locale()
    messages_for_lang = MESSAGES.get(target_lang, MESSAGES.get("en", {}))
    template = messages_for_lang.get(key, MESSAGES.get("en", {}).get(key, key))

    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return template

    return template
