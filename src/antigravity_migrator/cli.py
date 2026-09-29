"""Command-line interface for Antigravity Chat Migrator.

Provides audit, fix, watch, and rollback commands for managing Antigravity
conversations, project bindings, annotations, and protobuf caches.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Optional

from rich import box
from rich.console import Console
from rich.table import Table
import typer

from antigravity_migrator.backup_manager import BackupManager
from antigravity_migrator.i18n import (
    MESSAGES,
    get_current_locale,
    normalize_locale,
    set_current_locale,
    t,
)
from antigravity_migrator.paths import PathManager
from antigravity_migrator.process_watcher import (
    ProcessWatcher,
    get_running_pids,
    is_antigravity_running,
    wait_for_shutdown,
)
from antigravity_migrator.service import MigratorService
from antigravity_migrator.ui_renderer import (
    render_audit_table,
    render_banner,
    render_warning_cold_disk,
)

__version__ = "0.1.0"

# Extend bilingual dictionary with CLI-specific messages
MESSAGES["en"].update({
    "cli_dry_run_notice": "Simulation mode (dry-run). No changes will be written to disk.",
    "cli_fix_confirm": "Antigravity IDE is running. Writing now may corrupt data. Proceed anyway?",
    "cli_fix_aborted": "Operation aborted by user.",
    "cli_fix_waiting_ide": "Waiting for Antigravity IDE and Language Server to exit...",
    "cli_fix_ide_closed": "Antigravity IDE closed. Starting synchronization on cold disk...",
    "cli_fix_success": "Synchronization completed successfully.",
    "cli_fix_failed": "Synchronization completed with errors.",
    "cli_backup_created": "Safety snapshot created: {path}",
    "cli_scanned": "Conversations scanned: {count}",
    "cli_updated": "Conversations updated: {count}",
    "cli_annotations": "Annotations generated: {count}",
    "cli_projects": "Projects registered: {count}",
    "cli_watch_active": "Guardian active: watching Antigravity IDE lifecycle...",
    "cli_watch_running": "Antigravity IDE is currently active. Waiting for exit before sync...",
    "cli_watch_idle": "Antigravity IDE is not running. Performing synchronization...",
    "cli_rollback_title": "Available Recovery Snapshots",
    "cli_rollback_no_snapshots": "No recovery snapshots found in backup directory.",
    "cli_rollback_not_found": "Snapshot '{snapshot_id}' not found.",
    "cli_rollback_restoring": "Restoring snapshot '{snapshot_id}'...",
    "cli_rollback_success": "Snapshot '{snapshot_id}' successfully restored.",
    "cli_rollback_failed": "Failed to restore snapshot '{snapshot_id}'.",
    "cli_rollback_col_id": "Snapshot ID",
    "cli_rollback_col_date": "Created at",
    "cli_rollback_col_files": "Files",
    "cli_rollback_col_size": "Size",
})

MESSAGES["ru"].update({
    "cli_dry_run_notice": "Режим симуляции (dry-run). Изменения не будут записаны на диск.",
    "cli_fix_confirm": "Antigravity IDE активна. Запись может повредить данные. Все равно продолжить?",
    "cli_fix_aborted": "Операция отменена пользователем.",
    "cli_fix_waiting_ide": "Ожидание закрытия Antigravity IDE и языкового сервера...",
    "cli_fix_ide_closed": "Antigravity IDE закрыта. Запуск синхронизации на холодном диске...",
    "cli_fix_success": "Синхронизация успешно завершена.",
    "cli_fix_failed": "Синхронизация завершилась с ошибками.",
    "cli_backup_created": "Создан резервный снимок: {path}",
    "cli_scanned": "Просканировано диалогов: {count}",
    "cli_updated": "Обновлено диалогов: {count}",
    "cli_annotations": "Сгенерировано аннотаций: {count}",
    "cli_projects": "Зарегистрировано проектов: {count}",
    "cli_watch_active": "Сторож активен: отслеживание жизненного цикла Antigravity IDE...",
    "cli_watch_running": "Antigravity IDE активна. Ожидание завершения перед синхронизацией...",
    "cli_watch_idle": "Antigravity IDE не запущена. Выполнение синхронизации...",
    "cli_rollback_title": "Доступные резервные снимки",
    "cli_rollback_no_snapshots": "Резервные снимки не найдены в каталоге бэкапов.",
    "cli_rollback_not_found": "Снимок '{snapshot_id}' не найден.",
    "cli_rollback_restoring": "Восстановление снимка '{snapshot_id}'...",
    "cli_rollback_success": "Снимок '{snapshot_id}' успешно восстановлен.",
    "cli_rollback_failed": "Не удалось восстановить снимок '{snapshot_id}'.",
    "cli_rollback_col_id": "Идентификатор снимка",
    "cli_rollback_col_date": "Дата создания",
    "cli_rollback_col_files": "Файлов",
    "cli_rollback_col_size": "Размер",
})


app = typer.Typer(
    name="agy-migrator",
    help="Antigravity Chat Migrator & Workspace Synchronization Utility.",
    add_completion=False,
)

console = Console()

# Global state holder
_STATE: dict[str, Optional[str]] = {
    "data_dir": None,
    "config_dir": None,
    "lang": None,
}


def _get_path_manager() -> PathManager:
    """Construct PathManager using current CLI state."""
    return PathManager(
        data_dir=_STATE.get("data_dir"),
        config_dir=_STATE.get("config_dir"),
    )


def _format_size(size_bytes: int) -> str:
    """Format bytes into human readable size string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def version_callback(value: bool) -> None:
    """Print version and exit if --version is passed."""
    if value:
        console.print(f"[bold cyan]Antigravity Chat Migrator[/] [white]v{__version__}[/]")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show application version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
    lang: Optional[str] = typer.Option(
        None,
        "--lang",
        help="Interface language ('ru' or 'en').",
    ),
    data_dir: Optional[Path] = typer.Option(
        None,
        "--data-dir",
        help="Override Antigravity data directory (~/.gemini/antigravity).",
        hidden=True,
    ),
    config_dir: Optional[Path] = typer.Option(
        None,
        "--config-dir",
        help="Override Gemini config directory (~/.gemini/config).",
        hidden=True,
    ),
) -> None:
    """Antigravity Chat Migrator: synchronize chats and repair workspace bindings."""
    if lang:
        set_current_locale(lang)
        _STATE["lang"] = normalize_locale(lang)
    if data_dir:
        _STATE["data_dir"] = str(data_dir)
    if config_dir:
        _STATE["config_dir"] = str(config_dir)


@app.command("audit")
def audit_command() -> None:
    """Scan Antigravity conversations, workspace bindings, and annotations without changes."""
    active_lang = _STATE.get("lang") or get_current_locale()
    render_banner(console=console, lang=active_lang)

    pm = _get_path_manager()
    service = MigratorService(path_manager=pm)
    report = service.audit()

    render_audit_table(report=report, console=console, lang=active_lang)

    if report.unregistered_workspaces:
        console.print()
        console.print(f"[bold yellow]⚠️  {t('table_metric_unregistered', lang=active_lang)}:[/]")
        for ws in sorted(report.unregistered_workspaces):
            console.print(f"  • [cyan]{ws}[/]")


@app.command("fix")
def fix_command(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Simulate migration without modifying databases or files.",
    ),
    watch: bool = typer.Option(
        False,
        "--watch",
        help="Wait for running Antigravity IDE processes to exit before syncing.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Proceed with synchronization even if Antigravity is active.",
    ),
) -> None:
    """Repair conversation workspace bindings, generate annotations, and update caches."""
    active_lang = _STATE.get("lang") or get_current_locale()
    render_banner(console=console, lang=active_lang)

    if dry_run:
        console.print(f"[bold yellow]ℹ️  {t('cli_dry_run_notice', lang=active_lang)}[/]\n")

    watcher = ProcessWatcher()
    if not dry_run and is_antigravity_running():
        running_pids = get_running_pids()
        render_warning_cold_disk(console=console, lang=active_lang, pids=running_pids)

        if watch:
            console.print(f"[bold cyan]⏳ {t('cli_fix_waiting_ide', lang=active_lang)}[/]")
            exited = wait_for_shutdown()
            if not exited:
                console.print(f"[bold red]✖ {t('cli_fix_failed', lang=active_lang)}[/]")
                raise typer.Exit(code=1)
            console.print(f"[bold green]✔ {t('cli_fix_ide_closed', lang=active_lang)}[/]\n")
        elif not force:
            confirmed = typer.confirm(
                f"⚠️  {t('cli_fix_confirm', lang=active_lang)}",
                default=False,
            )
            if not confirmed:
                console.print(f"[bold red]✖ {t('cli_fix_aborted', lang=active_lang)}[/]")
                raise typer.Exit(code=1)
    elif dry_run and is_antigravity_running():
        # Informational only in simulation mode
        running_pids = get_running_pids()
        render_warning_cold_disk(console=console, lang=active_lang, pids=running_pids)

    pm = _get_path_manager()
    service = MigratorService(path_manager=pm)
    result = service.sync(dry_run=dry_run)

    console.print()
    if result.backup_path:
        console.print(f"[dim cyan]📦 {t('cli_backup_created', lang=active_lang, path=result.backup_path)}[/]")

    console.print(f"  • {t('cli_scanned', lang=active_lang, count=result.conversations_scanned)}")
    console.print(f"  • [green]{t('cli_updated', lang=active_lang, count=result.conversations_updated)}[/]")
    console.print(f"  • [cyan]{t('cli_annotations', lang=active_lang, count=result.annotations_created)}[/]")
    console.print(f"  • [magenta]{t('cli_projects', lang=active_lang, count=result.projects_registered)}[/]")

    if result.errors:
        console.print()
        for err in result.errors:
            console.print(f"[bold red]✖ {err}[/]")

    if result.success and not result.errors:
        console.print(f"\n[bold green]✔ {t('cli_fix_success', lang=active_lang)}[/]")
    else:
        console.print(f"\n[bold yellow]▲ {t('cli_fix_failed', lang=active_lang)}[/]")
        if not result.success:
            raise typer.Exit(code=1)


@app.command("watch")
def watch_command() -> None:
    """Monitor Antigravity IDE processes and automatically synchronize upon exit."""
    active_lang = _STATE.get("lang") or get_current_locale()
    render_banner(console=console, lang=active_lang)

    console.print(f"[bold cyan]👀 {t('cli_watch_active', lang=active_lang)}[/]\n")

    if is_antigravity_running():
        pids = get_running_pids()
        render_warning_cold_disk(console=console, lang=active_lang, pids=pids)
        console.print(f"[bold yellow]⏳ {t('cli_watch_running', lang=active_lang)}[/]")
        wait_for_shutdown()
        console.print(f"[bold green]✔ {t('cli_fix_ide_closed', lang=active_lang)}[/]\n")
    else:
        console.print(f"[dim]{t('cli_watch_idle', lang=active_lang)}[/]\n")

    pm = _get_path_manager()
    service = MigratorService(path_manager=pm)
    result = service.sync(dry_run=False)

    if result.backup_path:
        console.print(f"[dim cyan]📦 {t('cli_backup_created', lang=active_lang, path=result.backup_path)}[/]")

    console.print(f"  • {t('cli_scanned', lang=active_lang, count=result.conversations_scanned)}")
    console.print(f"  • [green]{t('cli_updated', lang=active_lang, count=result.conversations_updated)}[/]")
    console.print(f"  • [cyan]{t('cli_annotations', lang=active_lang, count=result.annotations_created)}[/]")
    console.print(f"  • [magenta]{t('cli_projects', lang=active_lang, count=result.projects_registered)}[/]")

    if result.success:
        console.print(f"\n[bold green]✔ {t('cli_fix_success', lang=active_lang)}[/]")
    else:
        console.print(f"\n[bold red]✖ {t('cli_fix_failed', lang=active_lang)}[/]")
        raise typer.Exit(code=1)


@app.command("rollback")
def rollback_command(
    snapshot_id: Optional[str] = typer.Argument(
        None,
        help="Snapshot ID or timestamp folder to restore (defaults to most recent).",
    ),
    list_snapshots_flag: bool = typer.Option(
        False,
        "--list",
        "-l",
        help="List all available recovery snapshots.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Proceed with rollback even if Antigravity is active.",
    ),
) -> None:
    """Restore Antigravity database and cache states from a safety backup snapshot."""
    active_lang = _STATE.get("lang") or get_current_locale()
    pm = _get_path_manager()
    bm = BackupManager(path_manager=pm)
    snapshots = bm.list_snapshots()

    if list_snapshots_flag or snapshot_id == "list":
        if not snapshots:
            console.print(f"[bold yellow]ℹ️  {t('cli_rollback_no_snapshots', lang=active_lang)}[/]")
            return

        table = Table(
            title=f"[bold white]{t('cli_rollback_title', lang=active_lang)}[/]",
            box=box.ROUNDED,
            border_style="bright_blue",
            header_style="bold cyan",
        )
        table.add_column(t("cli_rollback_col_id", lang=active_lang), style="bold white")
        table.add_column(t("cli_rollback_col_date", lang=active_lang), style="cyan")
        table.add_column(t("cli_rollback_col_files", lang=active_lang), justify="right")
        table.add_column(t("cli_rollback_col_size", lang=active_lang), justify="right")

        for snap in snapshots:
            table.add_row(
                snap["id"],
                str(snap.get("created_at", "")),
                str(snap.get("files_count", 0)),
                _format_size(snap.get("size_bytes", 0)),
            )

        console.print(table)
        return

    if not snapshots:
        console.print(f"[bold red]✖ {t('cli_rollback_no_snapshots', lang=active_lang)}[/]")
        raise typer.Exit(code=1)

    target_snapshot: Optional[dict[str, Any]] = None
    if snapshot_id:
        for snap in snapshots:
            if snap["id"] == snapshot_id:
                target_snapshot = snap
                break
        if target_snapshot is None:
            console.print(
                f"[bold red]✖ {t('cli_rollback_not_found', lang=active_lang, snapshot_id=snapshot_id)}[/]"
            )
            raise typer.Exit(code=1)
    else:
        # Default to most recent snapshot
        target_snapshot = snapshots[0]

    chosen_id = target_snapshot["id"]
    chosen_path = target_snapshot["path"]

    console.print(f"[bold cyan]🔄 {t('cli_rollback_restoring', lang=active_lang, snapshot_id=chosen_id)}[/]")

    if is_antigravity_running():
        render_warning_cold_disk(console=console, lang=active_lang, pids=get_running_pids())
        if not force:
            confirmed = typer.confirm(
                f"⚠️  {t('cli_fix_confirm', lang=active_lang)}",
                default=False,
            )
            if not confirmed:
                console.print(f"[bold red]✖ {t('cli_fix_aborted', lang=active_lang)}[/]")
                raise typer.Exit(code=1)

    success = bm.restore_snapshot(snapshot_path=chosen_path, target_data_dir=pm.data_dir)
    if success:
        console.print(f"[bold green]✔ {t('cli_rollback_success', lang=active_lang, snapshot_id=chosen_id)}[/]")
    else:
        console.print(f"[bold red]✖ {t('cli_rollback_failed', lang=active_lang, snapshot_id=chosen_id)}[/]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
