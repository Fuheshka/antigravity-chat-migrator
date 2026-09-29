"""High-level MigratorService for auditing, synchronization, and Protobuf/SQLite cache patching."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
import re
import time
from typing import Any, Optional, Union
import uuid

from antigravity_migrator.annotation_generator import AnnotationGenerator
from antigravity_migrator.backup_manager import BackupManager
from antigravity_migrator.db_manager import DatabaseManager
from antigravity_migrator.paths import PathManager
from antigravity_migrator.project_registry import (
    ProjectRegistry,
    normalize_workspace_uri,
)
from antigravity_migrator.proto_codec import (
    encode_field,
    inject_project_id_into_metadata,
    parse_proto,
)

logger = logging.getLogger(__name__)

__all__ = [
    "AuditReport",
    "SyncResult",
    "MigratorService",
]


@dataclass
class AuditReport:
    """Summary statistics from auditing Antigravity conversations and workspace mappings."""

    total_conversations: int = 0
    bound_to_projects: int = 0
    outside_of_project: int = 0
    missing_annotations: int = 0
    unregistered_workspaces: list[str] = field(default_factory=list)

    @property
    def unregistered_count(self) -> int:
        """Number of distinct unregistered workspaces."""
        return len(self.unregistered_workspaces)

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "total_conversations": self.total_conversations,
            "bound_to_projects": self.bound_to_projects,
            "outside_of_project": self.outside_of_project,
            "missing_annotations": self.missing_annotations,
            "unregistered_workspaces": list(self.unregistered_workspaces),
        }


@dataclass
class SyncResult:
    """Detailed result of running a project synchronization operation."""

    success: bool = True
    dry_run: bool = False
    backup_path: Optional[Path] = None
    conversations_scanned: int = 0
    conversations_updated: int = 0
    annotations_created: int = 0
    projects_registered: int = 0
    proto_cache_updated: bool = False
    summaries_db_updated: bool = False
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "success": self.success,
            "dry_run": self.dry_run,
            "backup_path": str(self.backup_path) if self.backup_path else None,
            "conversations_scanned": self.conversations_scanned,
            "conversations_updated": self.conversations_updated,
            "annotations_created": self.annotations_created,
            "projects_registered": self.projects_registered,
            "proto_cache_updated": self.proto_cache_updated,
            "summaries_db_updated": self.summaries_db_updated,
            "errors": list(self.errors),
        }


class MigratorService:
    """Unified service for auditing chat states, registering projects, and syncing Protobuf/SQLite caches."""

    def __init__(
        self,
        path_manager: Optional[PathManager] = None,
        data_dir: Optional[Union[Path, str]] = None,
        config_dir: Optional[Union[Path, str]] = None,
    ) -> None:
        if path_manager is not None:
            self.path_manager = path_manager
        else:
            self.path_manager = PathManager(data_dir=data_dir, config_dir=config_dir)

        self.project_registry = ProjectRegistry(path_manager=self.path_manager)
        self.backup_manager = BackupManager(path_manager=self.path_manager)
        self.db_manager = DatabaseManager()
        self.annotation_generator = AnnotationGenerator()

    def audit(self) -> AuditReport:
        """Scan Antigravity conversations directory and report stats on bindings, annotations, and workspaces."""
        report = AuditReport()
        conv_dir = self.path_manager.conversations_dir
        if not conv_dir.is_dir():
            return report

        db_files = sorted(conv_dir.glob("*.db"))
        report.total_conversations = len(db_files)

        unreg_set: set[str] = set()

        for db_file in db_files:
            cid = db_file.stem

            # 1. Check project binding in trajectory_metadata_blob (Field 18)
            pid = self.db_manager.extract_project_id(db_file)
            if pid and pid != "outside-of-project":
                report.bound_to_projects += 1
            else:
                report.outside_of_project += 1

            # 2. Check annotations
            ann_file = self.path_manager.annotations_dir / f"{cid}.pbtxt"
            if not ann_file.is_file():
                report.missing_annotations += 1

            # 3. Check workspace registration
            ws_uri = self.db_manager.extract_workspace_uri(db_file)
            if ws_uri:
                reg_pid = self.project_registry.get_project_id(ws_uri)
                if not reg_pid:
                    norm = normalize_workspace_uri(ws_uri)
                    if norm not in unreg_set:
                        unreg_set.add(norm)
                        report.unregistered_workspaces.append(norm)

        return report

    def sync(self, dry_run: bool = False, auto_register: bool = True) -> SyncResult:
        """Perform end-to-end synchronization across databases, annotations, and caches."""
        result = SyncResult(dry_run=dry_run)

        try:
            # 1. Create safety backup if not dry run
            if not dry_run:
                try:
                    result.backup_path = self.backup_manager.create_snapshot()
                except Exception as e:
                    logger.error("Failed to create snapshot backup: %s", e)
                    result.errors.append(f"Backup failed: {e}")
                    result.success = False
                    return result

            # 2. Match workspaces from conversations/*.db with ProjectRegistry
            conv_dir = self.path_manager.conversations_dir
            db_files = sorted(conv_dir.glob("*.db")) if conv_dir.is_dir() else []
            result.conversations_scanned = len(db_files)

            convo_pids: dict[str, str] = {}
            convo_titles: dict[str, str] = {}
            convo_raw_summaries: dict[str, bytes] = {}

            # Keep track of newly auto-registered workspaces during this sync run
            registered_cache: dict[str, str] = {}

            for db_file in db_files:
                cid = db_file.stem
                ws_uri = self.db_manager.extract_workspace_uri(db_file)
                target_pid = "outside-of-project"

                if ws_uri:
                    norm_ws = normalize_workspace_uri(ws_uri)
                    if norm_ws in registered_cache:
                        target_pid = registered_cache[norm_ws]
                    else:
                        existing_pid = self.project_registry.get_project_id(ws_uri)
                        if existing_pid:
                            target_pid = existing_pid
                            registered_cache[norm_ws] = existing_pid
                        elif auto_register:
                            if not dry_run:
                                target_pid = self.project_registry.register(ws_uri)
                            else:
                                target_pid = f"dry-run-project-{uuid.uuid4()}"
                            registered_cache[norm_ws] = target_pid
                            result.projects_registered += 1

                convo_pids[cid] = target_pid

                # 3. Update project_id in trajectory_metadata_blob of db_file
                current_pid = self.db_manager.extract_project_id(db_file)
                if current_pid != target_pid:
                    raw_blob = self.db_manager.read_trajectory_metadata(db_file) or b""
                    new_blob = inject_project_id_into_metadata(raw_blob, project_id=target_pid)
                    if not dry_run:
                        self.db_manager.update_trajectory_metadata(db_file, new_blob)
                    result.conversations_updated += 1

                # 4. Generate missing annotations via AnnotationGenerator
                ann_path = self.path_manager.annotations_dir / f"{cid}.pbtxt"
                title = None
                if ann_path.is_file():
                    try:
                        content = ann_path.read_text(encoding="utf-8")
                        m = re.search(r'title:\s*"([^"]+)"', content)
                        if m:
                            title = m.group(1)
                    except OSError:
                        pass

                if not title or not ann_path.is_file():
                    # Resolve transcript path
                    tr_path = self.path_manager.brain_dir / cid / ".system_generated" / "logs" / "transcript.jsonl"
                    if not tr_path.is_file():
                        alt_tr = self.path_manager.brain_dir / cid / "transcript.jsonl"
                        if alt_tr.is_file():
                            tr_path = alt_tr

                    extracted_title, ts = self.annotation_generator.extract_title_from_transcript(tr_path)
                    title = extracted_title
                    if not ann_path.is_file():
                        if ts is None:
                            ts = int(time.time())
                        if not dry_run:
                            self.annotation_generator.ensure_annotation_file(
                                ann_path, title=title, timestamp_seconds=ts
                            )
                        result.annotations_created += 1

                convo_titles[cid] = title or "Untitled Conversation"

            # 5. Patch binary cache agyhub_summaries_proto.pb
            pb_path = self.path_manager.summaries_pb
            if pb_path.is_file():
                try:
                    pb_data = pb_path.read_bytes()
                    top_entries = parse_proto(pb_data)
                    new_top_entries: list[bytes] = []

                    for fnum, wtype, entry_bytes in top_entries:
                        if fnum == 1 and wtype == 2 and isinstance(entry_bytes, (bytes, bytearray)):
                            entry_fields = parse_proto(entry_bytes)
                            entry_cid: str | None = None
                            entry_summary: bytes | None = None

                            for efn, ewt, evalue in entry_fields:
                                if efn == 1 and ewt == 2 and isinstance(evalue, (bytes, bytearray)):
                                    entry_cid = evalue.decode("utf-8", errors="ignore")
                                elif efn == 2 and ewt == 2 and isinstance(evalue, (bytes, bytearray)):
                                    entry_summary = bytes(evalue)

                            if entry_cid and entry_summary:
                                entry_pid = convo_pids.get(entry_cid, "outside-of-project")

                                # Update Field 17 in summary_bytes
                                s_fields = parse_proto(entry_summary)
                                new_s_fields: list[tuple[int, int, Any]] = []
                                has_17 = False

                                for sn, swt, sval in s_fields:
                                    if sn == 17 and swt == 2:
                                        has_17 = True
                                        rebuilt_meta = inject_project_id_into_metadata(
                                            sval, project_id=entry_pid
                                        )
                                        new_s_fields.append((17, 2, rebuilt_meta))
                                    else:
                                        new_s_fields.append((sn, swt, sval))

                                if not has_17:
                                    rebuilt_meta = inject_project_id_into_metadata(
                                        b"", project_id=entry_pid
                                    )
                                    new_s_fields.append((17, 2, rebuilt_meta))

                                rebuilt_summary = b"".join(
                                    encode_field(fn, wt, val) for fn, wt, val in new_s_fields
                                )
                                convo_raw_summaries[entry_cid] = rebuilt_summary

                                new_entry = (
                                    encode_field(1, 2, entry_cid.encode("utf-8"))
                                    + encode_field(2, 2, rebuilt_summary)
                                )
                                new_top_entries.append(encode_field(fnum, wtype, new_entry))
                            else:
                                new_top_entries.append(encode_field(fnum, wtype, entry_bytes))
                        else:
                            new_top_entries.append(encode_field(fnum, wtype, entry_bytes))

                    if not dry_run:
                        new_pb_data = b"".join(new_top_entries)
                        pb_path.write_bytes(new_pb_data)

                    result.proto_cache_updated = True
                except Exception as e:
                    logger.error("Failed to patch summaries proto cache: %s", e)
                    result.errors.append(f"Proto cache update failed: {e}")

            # 6. Update records in conversation_summaries.db
            summaries_db_path = self.path_manager.summaries_db
            try:
                for cid, pid in convo_pids.items():
                    title = convo_titles.get(cid, "Untitled Conversation")
                    raw_summary = convo_raw_summaries.get(cid)
                    if not dry_run:
                        self.db_manager.update_summary_record(
                            db_path=summaries_db_path,
                            conversation_id=cid,
                            title=title,
                            project_id=pid,
                            raw_summary=raw_summary,
                        )
                result.summaries_db_updated = True
            except Exception as e:
                logger.error("Failed to update conversation_summaries.db: %s", e)
                result.errors.append(f"Summaries DB update failed: {e}")

        except Exception as e:
            logger.exception("Unexpected error during sync: %s", e)
            result.errors.append(f"Unexpected sync error: {e}")
            result.success = False

        return result
