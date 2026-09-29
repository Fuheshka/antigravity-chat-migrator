"""Rich UI rendering components for terminal tables, banners, warnings, and progress."""

from __future__ import annotations

from typing import Optional

from rich import box
from rich.align import Align
from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

from antigravity_migrator.i18n import t
from antigravity_migrator.service import AuditReport

__version__ = "0.1.0"

__all__ = [
    "render_banner",
    "render_audit_table",
    "render_warning_cold_disk",
    "render_sync_progress",
]

ASCII_LOGO = r"""
   ___          __  _                         _  __       
  / _ | ___  __/ /_(_)__ ________ __  _____ _(_)/ /___ __ 
 / __ |/ _ \/ _  / // _ `/ __/ _ `/ |/ / // / // __/ // / 
/_/ |_/_//_/\_,_/_/ \_, /_/  \_,_/|___/\_, /_//_/  \_, /  
                   /___/              /___/       /___/   
"""


def render_banner(
    console: Optional[Console] = None,
    lang: Optional[str] = None,
) -> Panel:
    """Render a stylish high-contrast ASCII art banner with application version.

    Args:
        console: Optional Rich Console instance to print banner to.
        lang: Optional locale override ('ru' or 'en').

    Returns:
        Rich Panel renderable containing the banner.
    """
    version_text = t("banner_version", lang=lang, version=__version__)
    subtitle_text = t("banner_subtitle", lang=lang)
    rule_text = t("banner_rule_cold_disk", lang=lang)

    content = Text()
    content.append(ASCII_LOGO.strip("\n"), style="bold cyan")
    content.append("\n\n")
    content.append(f"  ⚡ {subtitle_text}\n", style="bold white")
    content.append(f"  📦 {version_text}   •   🛡️ {rule_text}\n", style="dim cyan")

    panel = Panel(
        Align.center(content),
        box=box.ROUNDED,
        border_style="bright_blue",
        padding=(1, 2),
    )

    if console is not None:
        console.print(panel)

    return panel


def render_audit_table(
    report: AuditReport,
    console: Optional[Console] = None,
    lang: Optional[str] = None,
) -> Table:
    """Render a contrast-optimized audit summary table.

    Args:
        report: AuditReport instance with diagnostic metrics.
        console: Optional Rich Console instance to print table to.
        lang: Optional locale override ('ru' or 'en').

    Returns:
        Rich Table renderable.
    """
    title_text = t("table_title", lang=lang)
    col_metric = t("table_col_metric", lang=lang)
    col_count = t("table_col_count", lang=lang)
    col_status = t("table_col_status", lang=lang)

    status_ok = t("table_status_ok", lang=lang)
    status_warn = t("table_status_warning", lang=lang)
    status_fix = t("table_status_fixed", lang=lang)
    status_ready = t("table_status_ready", lang=lang)

    table = Table(
        title=f"[bold white]{title_text}[/]",
        box=box.ROUNDED,
        header_style="bold cyan",
        title_style="bold white",
        border_style="bright_blue",
        show_edge=True,
    )

    table.add_column(col_metric, style="white", min_width=36)
    table.add_column(col_count, justify="right", style="bold cyan", min_width=10)
    table.add_column(col_status, justify="center", min_width=20)

    # 1. Total conversations
    table.add_row(
        t("table_metric_total", lang=lang),
        str(report.total_conversations),
        f"[green]✔ {status_ready}[/]" if report.total_conversations > 0 else f"[dim]{status_ok}[/]",
    )

    # 2. Bound to projects
    table.add_row(
        t("table_metric_bound", lang=lang),
        str(report.bound_to_projects),
        f"[green]✔ {status_ok}[/]",
    )

    # 3. Outside of project
    if report.outside_of_project > 0:
        table.add_row(
            f"[bold yellow]{t('table_metric_outside', lang=lang)}[/]",
            f"[bold yellow]{report.outside_of_project}[/]",
            f"[bold yellow]▲ {status_warn}[/]",
        )
    else:
        table.add_row(
            t("table_metric_outside", lang=lang),
            "0",
            f"[green]✔ {status_ok}[/]",
        )

    # 4. Missing annotations
    if report.missing_annotations > 0:
        table.add_row(
            f"[bold magenta]{t('table_metric_missing_anno', lang=lang)}[/]",
            f"[bold magenta]{report.missing_annotations}[/]",
            f"[cyan]↻ {status_fix}[/]",
        )
    else:
        table.add_row(
            t("table_metric_missing_anno", lang=lang),
            "0",
            f"[green]✔ {status_ok}[/]",
        )

    # 5. Unregistered workspaces
    unregistered_count = report.unregistered_count
    if unregistered_count > 0:
        table.add_row(
            f"[bold red]{t('table_metric_unregistered', lang=lang)}[/]",
            f"[bold red]{unregistered_count}[/]",
            f"[bold red]✖ {status_warn}[/]",
        )
    else:
        table.add_row(
            t("table_metric_unregistered", lang=lang),
            "0",
            f"[green]✔ {status_ok}[/]",
        )

    if console is not None:
        console.print(table)

    return table


def render_warning_cold_disk(
    console: Optional[Console] = None,
    lang: Optional[str] = None,
    pids: Optional[list[int]] = None,
) -> Panel:
    """Render a high-visibility warning panel urging the user to close active IDE processes.

    Args:
        console: Optional Rich Console instance to print warning to.
        lang: Optional locale override ('ru' or 'en').
        pids: Optional list of detected running PIDs.

    Returns:
        Rich Panel renderable.
    """
    title_text = t("warning_cold_disk_title", lang=lang)
    body_text = t("warning_cold_disk_body", lang=lang)
    advice_text = t("warning_cold_disk_advice", lang=lang)

    text = Text()
    text.append(f"⚠️  {body_text}\n\n", style="bold yellow")
    text.append(f"👉 {advice_text}\n", style="bold white")

    if pids:
        pids_str = ", ".join(str(p) for p in sorted(pids))
        pid_msg = t("warning_active_pids", lang=lang, pids=pids_str)
        text.append(f"\n🔍 {pid_msg}\n", style="bold red")

    panel = Panel(
        text,
        title=f"[bold red] {title_text} [/]",
        title_align="center",
        box=box.HEAVY,
        border_style="bold red",
        padding=(1, 2),
    )

    if console is not None:
        console.print(panel)

    return panel


def render_sync_progress(
    console: Optional[Console] = None,
    lang: Optional[str] = None,
) -> Progress:
    """Create and return a styled Rich Progress instance for migration steps.

    Args:
        console: Optional Rich Console instance to bind progress to.
        lang: Optional locale override ('ru' or 'en').

    Returns:
        Configured rich.progress.Progress instance.
    """
    progress_console = console or Console()
    return Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(bar_width=36, style="grey37", complete_style="bold green"),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=progress_console,
        transient=False,
    )
