"""Typed GUI Bridge API adapter connecting JavaScript frontend to Antigravity Migrator core."""

from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path
import platform
import re
from typing import Any, Dict, List, Optional, Union
from urllib.parse import unquote

from antigravity_migrator import __version__
from antigravity_migrator.backup_manager import BackupManager
from antigravity_migrator.i18n import detect_locale, t
from antigravity_migrator.paths import PathManager
from antigravity_migrator.process_watcher import ProcessWatcher
from antigravity_migrator.project_registry import (
    ProjectRegistry,
    normalize_workspace_uri,
)
from antigravity_migrator.service import AuditReport, MigratorService, SyncResult
from antigravity_migrator.updater import (
    check_github_update,
    open_update_url as updater_open_url,
)

logger = logging.getLogger(__name__)

__all__ = ["GuiBridgeApi"]


class GuiBridgeApi:
    """Safe, typed bridge API exposed to the pywebview JavaScript runtime."""

    def __init__(
        self,
        service: Optional[MigratorService] = None,
        process_watcher: Optional[ProcessWatcher] = None,
        backup_manager: Optional[BackupManager] = None,
        path_manager: Optional[PathManager] = None,
    ) -> None:
        self.path_manager = path_manager or PathManager()
        self.service = service or MigratorService(path_manager=self.path_manager)
        self.process_watcher = process_watcher or ProcessWatcher()
        self.backup_manager = backup_manager or getattr(
            self.service, "backup_manager", BackupManager(path_manager=self.path_manager)
        )
        self.project_registry = getattr(
            self.service, "project_registry", ProjectRegistry(path_manager=self.path_manager)
        )

    def get_system_info(self) -> Dict[str, Any]:
        """Return operating system, app version, default language, and Antigravity directory paths."""
        try:
            return {
                "os": platform.system(),
                "os_version": platform.version(),
                "platform": platform.platform(),
                "app_version": __version__,
                "locale": detect_locale(),
                "paths": {
                    "data_dir": str(self.path_manager.data_dir),
                    "config_dir": str(self.path_manager.config_dir),
                    "projects_dir": str(self.path_manager.projects_dir),
                    "conversations_dir": str(self.path_manager.conversations_dir),
                    "annotations_dir": str(self.path_manager.annotations_dir),
                    "brain_dir": str(self.path_manager.brain_dir),
                    "backups_dir": str(self.path_manager.backups_dir),
                    "summaries_db": str(self.path_manager.summaries_db),
                    "summaries_pb": str(self.path_manager.summaries_pb),
                },
            }
        except Exception as e:
            logger.exception("Error in get_system_info: %s", e)
            return {
                "os": platform.system(),
                "os_version": "",
                "platform": "",
                "app_version": __version__,
                "locale": "en",
                "paths": {},
                "error": str(e),
            }

    def get_process_status(self) -> Dict[str, Any]:
        """Return Antigravity process status: is_running, list of active PIDs, and warning text."""
        try:
            pids = self.process_watcher.get_pids()
            is_running = len(pids) > 0 or self.process_watcher.is_running()
            warning: Optional[str] = None

            if is_running:
                loc = detect_locale()
                pids_str = ", ".join(str(p) for p in pids) if pids else "active"
                warning_body = t("warning_cold_disk_body", loc)
                warning_pids = t("warning_active_pids", loc, pids=pids_str)
                warning = f"{warning_body} {warning_pids}".strip()

            return {
                "is_running": is_running,
                "pids": pids,
                "warning": warning,
            }
        except Exception as e:
            logger.exception("Error in get_process_status: %s", e)
            return {
                "is_running": False,
                "pids": [],
                "warning": None,
                "error": str(e),
            }

    def _load_project_names(self) -> Dict[str, str]:
        """Build dictionary mapping project_id to user-friendly project name."""
        names: Dict[str, str] = {}
        projects_dir = self.path_manager.projects_dir
        if not projects_dir.is_dir():
            return names

        for pfile in projects_dir.glob("*.json"):
            if pfile.stem == "outside-of-project":
                continue
            try:
                data = json.loads(pfile.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    pid = data.get("id")
                    pname = data.get("name")
                    if pid and pname:
                        names[str(pid)] = str(pname)
            except Exception:
                continue
        return names

    def _extract_conversations_details(self) -> List[Dict[str, Any]]:
        """Extract detailed information for every conversation database."""
        conv_dir = self.path_manager.conversations_dir
        if not conv_dir.is_dir():
            return []

        db_files = sorted(conv_dir.glob("*.db"))
        project_names = self._load_project_names()

        # Try reading titles from conversation_summaries.db
        summaries_map: Dict[str, Dict[str, Any]] = {}
        try:
            from antigravity_migrator.db_manager import DatabaseManager

            summaries_map = DatabaseManager.load_conversation_summaries(
                self.path_manager.summaries_db
            )
        except Exception:
            pass

        registered_map = self.project_registry.load_projects()
        conversations: List[Dict[str, Any]] = []

        for db_file in db_files:
            cid = db_file.stem
            ws_uri = self.service.db_manager.extract_workspace_uri(db_file)
            pid = self.service.db_manager.extract_project_id(db_file)

            # Determine title
            title: str = ""
            if cid in summaries_map and summaries_map[cid].get("title"):
                title = summaries_map[cid]["title"]

            ann_file = self.path_manager.annotations_dir / f"{cid}.pbtxt"
            annotation_exists = ann_file.is_file()
            if not title and annotation_exists:
                try:
                    content = ann_file.read_text(encoding="utf-8")
                    m = re.search(r'title:\s*"([^"]+)"', content)
                    if m:
                        title = m.group(1)
                except Exception:
                    pass

            if not title:
                # Check transcript
                tr_path = (
                    self.path_manager.brain_dir
                    / cid
                    / ".system_generated"
                    / "logs"
                    / "transcript.jsonl"
                )
                if not tr_path.is_file():
                    tr_path = self.path_manager.brain_dir / cid / "transcript.jsonl"
                if tr_path.is_file():
                    extracted_title, _ = (
                        self.service.annotation_generator.extract_title_from_transcript(tr_path)
                    )
                    title = extracted_title or ""

            if not title:
                title = "Untitled Conversation"

            # Determine workspace registration
            is_unregistered = False
            if ws_uri:
                norm_ws = normalize_workspace_uri(ws_uri)
                if norm_ws not in registered_map:
                    is_unregistered = True

            # Determine project name
            project_name: Optional[str] = None
            if pid and pid != "outside-of-project":
                project_name = project_names.get(pid)
                if not project_name and ws_uri:
                    # Fallback to directory name
                    norm_path = Path(unquote(normalize_workspace_uri(ws_uri).replace("file://", "")))
                    project_name = norm_path.name
            elif pid == "outside-of-project":
                project_name = "Outside of Project"

            # Determine status
            if not pid or pid == "outside-of-project":
                status = "outside_of_project"
            elif not annotation_exists:
                status = "missing_annotation"
            elif is_unregistered:
                status = "unregistered_workspace"
            else:
                status = "ok"

            conversations.append({
                "id": cid,
                "title": title,
                "workspace_uri": ws_uri,
                "project_id": pid,
                "project_name": project_name,
                "status": status,
            })

        return conversations

    def run_audit(self) -> Dict[str, Any]:
        """Perform a full scan of conversations, workspace bindings, and annotations."""
        try:
            report: AuditReport = self.service.audit()
            conversations = self._extract_conversations_details()

            return {
                "total_conversations": report.total_conversations,
                "bound_to_projects": report.bound_to_projects,
                "outside_of_project": report.outside_of_project,
                "missing_annotations": report.missing_annotations,
                "unregistered_workspaces": list(report.unregistered_workspaces),
                "conversations": conversations,
            }
        except Exception as e:
            logger.exception("Error in run_audit: %s", e)
            return {
                "total_conversations": 0,
                "bound_to_projects": 0,
                "outside_of_project": 0,
                "missing_annotations": 0,
                "unregistered_workspaces": [],
                "conversations": [],
                "error": str(e),
            }

    def run_fix(self, dry_run: bool = False, auto_register: bool = True) -> Dict[str, Any]:
        """Execute synchronization and repair (or simulation if dry_run=True)."""
        try:
            sync_result: SyncResult = self.service.sync(
                dry_run=dry_run, auto_register=auto_register
            )
            res_dict = sync_result.to_dict()
            return res_dict
        except Exception as e:
            logger.exception("Error in run_fix: %s", e)
            return {
                "success": False,
                "dry_run": dry_run,
                "backup_path": None,
                "conversations_scanned": 0,
                "conversations_updated": 0,
                "annotations_created": 0,
                "projects_registered": 0,
                "proto_cache_updated": False,
                "summaries_db_updated": False,
                "errors": [str(e)],
                "error": str(e),
            }

    def list_backups(self) -> List[Dict[str, Any]]:
        """Return list of available safety snapshots with formatted dates and sizes."""
        try:
            snapshots = self.backup_manager.list_snapshots()
            items: List[Dict[str, Any]] = []

            for s in snapshots:
                snap_id = str(s.get("id", ""))
                created_raw = s.get("created_at")

                date_formatted = snap_id
                timestamp = 0.0

                # Try parsing standard snapshot folder format: YYYY-MM-DD_HH-MM-SS
                try:
                    dt = datetime.strptime(snap_id[:19], "%Y-%m-%d_%H-%M-%S")
                    date_formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
                    timestamp = dt.timestamp()
                except Exception:
                    if isinstance(created_raw, str):
                        try:
                            dt = datetime.fromisoformat(created_raw)
                            date_formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
                            timestamp = dt.timestamp()
                        except Exception:
                            date_formatted = created_raw
                    elif isinstance(created_raw, (int, float)):
                        timestamp = float(created_raw)
                        date_formatted = datetime.fromtimestamp(timestamp).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )

                items.append({
                    "id": snap_id,
                    "timestamp": timestamp,
                    "date_formatted": date_formatted,
                    "files_count": int(s.get("files_count", 0)),
                    "size_bytes": int(s.get("size_bytes", 0)),
                    "path": str(s.get("path", "")),
                })

            return items
        except Exception as e:
            logger.exception("Error in list_backups: %s", e)
            return []

    def restore_backup(self, snapshot_id: str) -> Dict[str, Any]:
        """Safely restore a snapshot, enforcing the cold-disk invariant before writing."""
        try:
            # 1. Enforce cold-disk invariant
            if self.process_watcher.is_running():
                loc = detect_locale()
                return {
                    "success": False,
                    "snapshot_id": snapshot_id,
                    "cold_disk_violation": True,
                    "error": (
                        f"{t('warning_cold_disk_title', loc)}: {t('warning_cold_disk_body', loc)}"
                    ),
                }

            # 2. Resolve snapshot directory
            candidate_path = Path(snapshot_id)
            if candidate_path.is_absolute() and candidate_path.exists():
                target_snap = candidate_path
            else:
                target_snap = self.backup_manager.backup_dir / snapshot_id

            # 3. Perform restoration
            success = self.backup_manager.restore_snapshot(target_snap)
            return {
                "success": bool(success),
                "snapshot_id": snapshot_id,
                "error": None if success else "Failed to restore snapshot files or verify integrity",
            }
        except Exception as e:
            logger.exception("Error in restore_backup: %s", e)
            return {
                "success": False,
                "snapshot_id": snapshot_id,
                "error": str(e),
            }

    def check_for_updates(self, force: bool = False) -> Dict[str, Any]:
        """Check for application updates via GitHub Releases API."""
        try:
            return check_github_update(
                current_version=__version__,
                force=force,
            )
        except Exception as e:
            logger.exception("Error in check_for_updates: %s", e)
            return {
                "update_available": False,
                "current_version": __version__,
                "latest_version": __version__,
                "download_url": "",
                "release_notes": "",
                "published_at": "",
                "throttled": False,
                "checked": False,
                "error": str(e),
            }

    def open_update_url(self, url: str) -> Dict[str, Any]:
        """Open release download page in the default web browser."""
        try:
            success = updater_open_url(url)
            return {"success": success, "url": url}
        except Exception as e:
            logger.exception("Error in open_update_url: %s", e)
            return {"success": False, "url": url, "error": str(e)}

