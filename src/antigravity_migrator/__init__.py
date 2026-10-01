"""Antigravity Chat Migrator & Project Sync Utility."""

__version__ = "0.1.0"

from antigravity_migrator.paths import PathManager
from antigravity_migrator.proto_codec import (
    build_workspace_info,
    encode_field,
    encode_varint,
    inject_project_id_into_metadata,
    parse_proto,
)
from antigravity_migrator.db_manager import (
    DatabaseManager,
    extract_workspace_uri,
    load_conversation_summaries,
    update_summary_record,
    update_trajectory_metadata,
)
from antigravity_migrator.annotation_generator import (
    AnnotationGenerator,
    ensure_annotation_file,
    extract_title_from_transcript,
    generate_annotation_pbtxt,
)
from antigravity_migrator.project_registry import (
    ProjectRegistry,
    load_registered_projects,
    normalize_workspace_uri,
    register_new_project,
)
from antigravity_migrator.backup_manager import (
    BackupManager,
    create_snapshot,
    list_snapshots,
    restore_snapshot,
)
from antigravity_migrator.process_watcher import (
    ProcessWatcher,
    get_running_pids,
    is_antigravity_process_name,
    is_antigravity_running,
    wait_for_shutdown,
)
from antigravity_migrator.service import (
    AuditReport,
    MigratorService,
    SyncResult,
)
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
from antigravity_migrator.gui_api import GuiBridgeApi
from antigravity_migrator.gui import (
    get_gui_asset_dir,
    get_gui_index_path,
    launch_gui,
)
from antigravity_migrator.updater import (
    check_github_update,
    get_platform_asset_url,
    is_version_newer,
    open_update_url,
)
from antigravity_migrator.cli import app

__all__ = [
    "app",
    "check_github_update",
    "get_platform_asset_url",
    "is_version_newer",
    "open_update_url",
    "GuiBridgeApi",
    "launch_gui",
    "get_gui_asset_dir",
    "get_gui_index_path",
    "PathManager",
    "DatabaseManager",
    "extract_workspace_uri",
    "extract_project_id",
    "read_trajectory_metadata",
    "update_trajectory_metadata",
    "load_conversation_summaries",
    "update_summary_record",
    "parse_proto",
    "encode_varint",
    "encode_field",
    "build_workspace_info",
    "inject_project_id_into_metadata",
    "AnnotationGenerator",
    "extract_title_from_transcript",
    "generate_annotation_pbtxt",
    "ensure_annotation_file",
    "ProjectRegistry",
    "load_registered_projects",
    "normalize_workspace_uri",
    "register_new_project",
    "BackupManager",
    "create_snapshot",
    "list_snapshots",
    "restore_snapshot",
    "ProcessWatcher",
    "is_antigravity_process_name",
    "get_running_pids",
    "is_antigravity_running",
    "wait_for_shutdown",
    "MigratorService",
    "AuditReport",
    "SyncResult",
    "MESSAGES",
    "detect_locale",
    "get_current_locale",
    "set_current_locale",
    "normalize_locale",
    "t",
    "render_banner",
    "render_audit_table",
    "render_warning_cold_disk",
    "render_sync_progress",
]

