"""Database manager for Antigravity SQLite databases.

Handles reading and safely updating individual conversation databases
(`conversations/<uuid>.db`) and the central registry (`conversation_summaries.db`)
with transactional integrity and SQLite busy_timeout protection.
"""

from __future__ import annotations

import contextlib
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional, Union

from antigravity_migrator.proto_codec import parse_proto

__all__ = [
    "DatabaseManager",
    "extract_workspace_uri",
    "extract_project_id",
    "read_trajectory_metadata",
    "update_trajectory_metadata",
    "load_conversation_summaries",
    "update_summary_record",
]

BUSY_TIMEOUT_MS = 5000
CONNECT_TIMEOUT_SEC = 5.0


@contextlib.contextmanager
def _open_db(path: Union[Path, str]):
    """Context manager for SQLite connections ensuring clean closure on Windows & POSIX."""
    conn = sqlite3.connect(str(path), timeout=CONNECT_TIMEOUT_SEC)
    try:
        conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        yield conn
        conn.commit()
    finally:
        conn.close()


class DatabaseManager:
    """Manager for Antigravity SQLite databases."""

    @staticmethod
    def extract_workspace_uri(db_path: Union[Path, str]) -> Optional[str]:
        """Extract workspace URI from trajectory_metadata_blob (id = 'main').

        Checks Field 1 (WorkspaceInfo message, subfield 1 = URI) and Field 7 (URI).
        Returns the workspace URI string, or None if not found or on error.
        """
        path = Path(db_path)
        if not path.is_file():
            return None

        try:
            with _open_db(path) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT data FROM trajectory_metadata_blob WHERE id = 'main'"
                )
                row = cur.fetchone()
                if not row or not row[0]:
                    return None

                raw_blob = row[0]
                fields = parse_proto(raw_blob)

                # 1. Check Field 1 (WorkspaceInfo)
                for fnum, wtype, payload in fields:
                    if fnum == 1 and wtype == 2:
                        if isinstance(payload, (bytes, bytearray)):
                            subfields = parse_proto(payload)
                            for sf_num, sf_wtype, sf_payload in subfields:
                                if sf_num == 1 and sf_wtype == 2 and isinstance(sf_payload, (bytes, bytearray)):
                                    uri = sf_payload.decode("utf-8", errors="replace").strip()
                                    if uri:
                                        return uri
                            # Fallback: check if payload itself is UTF-8 URI
                            try_str = payload.decode("utf-8", errors="ignore").strip()
                            if try_str.startswith("file://"):
                                return try_str

                # 2. Check Field 7 (direct workspace_uri)
                for fnum, wtype, payload in fields:
                    if fnum == 7 and wtype == 2 and isinstance(payload, (bytes, bytearray)):
                        uri = payload.decode("utf-8", errors="replace").strip()
                        if uri:
                            return uri

                return None
        except Exception:
            return None

    @staticmethod
    def read_trajectory_metadata(db_path: Union[Path, str]) -> Optional[bytes]:
        """Read the raw Protobuf blob from trajectory_metadata_blob (id = 'main')."""
        path = Path(db_path)
        if not path.is_file():
            return None
        try:
            with _open_db(path) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT data FROM trajectory_metadata_blob WHERE id = 'main'"
                )
                row = cur.fetchone()
                if row and row[0]:
                    return bytes(row[0])
                return None
        except Exception:
            return None

    @staticmethod
    def extract_project_id(db_path: Union[Path, str]) -> Optional[str]:
        """Extract project_id (Field 18) from trajectory_metadata_blob (id = 'main')."""
        raw_blob = DatabaseManager.read_trajectory_metadata(db_path)
        if not raw_blob:
            return None
        try:
            fields = parse_proto(raw_blob)
            for fnum, wtype, payload in fields:
                if fnum == 18 and wtype == 2 and isinstance(payload, (bytes, bytearray)):
                    pid = payload.decode("utf-8", errors="replace").strip()
                    if pid:
                        return pid
            return None
        except Exception:
            return None

    @staticmethod
    def update_trajectory_metadata(
        db_path: Union[Path, str], new_blob: bytes
    ) -> bool:
        """Atomically update or insert the Protobuf blob in trajectory_metadata_blob."""
        path = Path(db_path)
        try:
            if not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)

            with _open_db(path) as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS trajectory_metadata_blob ("
                    "id TEXT PRIMARY KEY DEFAULT 'main', "
                    "data BLOB"
                    ")"
                )
                conn.execute(
                    "INSERT OR REPLACE INTO trajectory_metadata_blob (id, data) VALUES ('main', ?)",
                    (new_blob,),
                )
            return True
        except Exception:
            return False

    @staticmethod
    def load_conversation_summaries(
        db_path: Union[Path, str]
    ) -> Dict[str, Dict[str, Any]]:
        """Load conversation summaries mapping conversation_id -> record dict.

        Returns empty dict if database or table does not exist.
        """
        path = Path(db_path)
        if not path.is_file():
            return {}

        try:
            with _open_db(path) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='conversation_summaries'"
                )
                if not cur.fetchone():
                    return {}

                cur.execute(
                    "SELECT conversation_id, title, project_id, raw_summary "
                    "FROM conversation_summaries"
                )
                rows = cur.fetchall()
                result: Dict[str, Dict[str, Any]] = {}
                for cid, title, pid, raw_summary in rows:
                    if cid:
                        result[cid] = {
                            "id": cid,
                            "conversation_id": cid,
                            "title": title or "",
                            "project_id": pid or "",
                            "raw_summary": raw_summary,
                        }
                return result
        except Exception:
            return {}

    @staticmethod
    def update_summary_record(
        db_path: Union[Path, str],
        conversation_id: str,
        title: Optional[str] = None,
        project_id: Optional[str] = None,
        raw_summary: Optional[bytes] = None,
    ) -> bool:
        """Update an existing record or insert a new one in conversation_summaries.

        If title, project_id, or raw_summary is None during an update, that column
        remains unchanged.
        """
        path = Path(db_path)
        try:
            if not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)

            with _open_db(path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conversation_summaries (
                        conversation_id TEXT PRIMARY KEY,
                        title TEXT NOT NULL DEFAULT '',
                        preview TEXT NOT NULL DEFAULT '',
                        step_count INTEGER NOT NULL DEFAULT 0,
                        last_modified_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        workspace_uris TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL DEFAULT '',
                        source TEXT NOT NULL DEFAULT '',
                        project_id TEXT NOT NULL DEFAULT '',
                        agent_name TEXT NOT NULL DEFAULT '',
                        parent_conversation_id TEXT NOT NULL DEFAULT '',
                        nesting_depth INTEGER NOT NULL DEFAULT 0,
                        battle_id TEXT NOT NULL DEFAULT '',
                        winning_conversation_id TEXT NOT NULL DEFAULT '',
                        not_fully_idle NUMERIC NOT NULL DEFAULT 0,
                        killed NUMERIC NOT NULL DEFAULT 0,
                        last_user_input_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        last_user_input_step_index INTEGER NOT NULL DEFAULT -1,
                        app_data_dir TEXT NOT NULL DEFAULT '',
                        raw_summary BLOB,
                        group_id TEXT NOT NULL DEFAULT ''
                    )
                    """
                )
                cur = conn.cursor()
                cur.execute(
                    "SELECT 1 FROM conversation_summaries WHERE conversation_id = ?",
                    (conversation_id,),
                )
                exists = cur.fetchone() is not None

                if exists:
                    updates = []
                    params: list[Any] = []
                    if title is not None:
                        updates.append("title = ?")
                        params.append(title)
                    if project_id is not None:
                        updates.append("project_id = ?")
                        params.append(project_id)
                    if raw_summary is not None:
                        updates.append("raw_summary = ?")
                        params.append(raw_summary)

                    if updates:
                        updates.append("last_modified_time = CURRENT_TIMESTAMP")
                        params.append(conversation_id)
                        sql = f"UPDATE conversation_summaries SET {', '.join(updates)} WHERE conversation_id = ?"
                        conn.execute(sql, tuple(params))
                else:
                    conn.execute(
                        """
                        INSERT INTO conversation_summaries (
                            conversation_id, title, project_id, raw_summary,
                            last_modified_time, last_user_input_time
                        ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        """,
                        (
                            conversation_id,
                            title or "",
                            project_id or "",
                            raw_summary,
                        ),
                    )
            return True
        except Exception:
            return False


# Module-level aliases
extract_workspace_uri = DatabaseManager.extract_workspace_uri
extract_project_id = DatabaseManager.extract_project_id
read_trajectory_metadata = DatabaseManager.read_trajectory_metadata
update_trajectory_metadata = DatabaseManager.update_trajectory_metadata
load_conversation_summaries = DatabaseManager.load_conversation_summaries
update_summary_record = DatabaseManager.update_summary_record
