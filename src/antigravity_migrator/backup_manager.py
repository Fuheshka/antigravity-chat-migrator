"""BackupManager for Antigravity data directories (atomic snapshots and rollback)."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import platform
import shutil
import subprocess
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from antigravity_migrator.paths import PathManager

logger = logging.getLogger(__name__)

TARGET_FILES = ("agyhub_summaries_proto.pb", "conversation_summaries.db")
TARGET_DIRS = ("annotations", "conversations")
MANIFEST_FILENAME = "manifest.json"


def _hash_file(path: Path) -> str:
    """Calculate SHA-256 hex digest of a file."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def _copy_item(src: Path, dst: Path, use_cow: bool = True) -> None:
    """Copy a file or directory, attempting macOS APFS clonefile (cp -c) first."""
    is_darwin = platform.system() == "Darwin"

    if is_darwin and use_cow:
        try:
            if src.is_dir():
                dst.mkdir(parents=True, exist_ok=True)
                subprocess.run(
                    ["cp", "-Rc", f"{src}/.", str(dst)],
                    check=True,
                    capture_output=True,
                )
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(
                    ["cp", "-c", str(src), str(dst)],
                    check=True,
                    capture_output=True,
                )
            return
        except (subprocess.CalledProcessError, FileNotFoundError, OSError):
            # Fall back to standard python copy if APFS clonefile fails
            pass

    # Standard cross-platform copy
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def create_snapshot(data_dir: Path | str, backup_dir: Path | str | None = None) -> Path:
    """Create an atomic snapshot of Antigravity summaries, annotations, and conversations.

    Args:
        data_dir: Antigravity data directory (~/.gemini/antigravity).
        backup_dir: Target backup directory (defaults to data_dir/.backups).

    Returns:
        Path to the created snapshot directory.
    """
    src_data_dir = Path(data_dir)
    target_backup_dir = Path(backup_dir) if backup_dir is not None else src_data_dir / ".backups"

    timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    snapshot_dir = target_backup_dir / timestamp_str

    # In case multiple snapshots are created within the same second
    counter = 1
    while snapshot_dir.exists():
        snapshot_dir = target_backup_dir / f"{timestamp_str}_{counter}"
        counter += 1

    snapshot_dir.mkdir(parents=True, exist_ok=True)

    manifest_files: dict[str, dict[str, Any]] = {}
    total_bytes = 0

    # 1. Copy individual files
    for filename in TARGET_FILES:
        file_path = src_data_dir / filename
        if file_path.is_file():
            dest_path = snapshot_dir / filename
            _copy_item(file_path, dest_path)
            size = dest_path.stat().st_size
            sha256 = _hash_file(dest_path)
            manifest_files[filename] = {"size": size, "sha256": sha256}
            total_bytes += size

    # 2. Copy directories
    for dirname in TARGET_DIRS:
        dir_path = src_data_dir / dirname
        if dir_path.is_dir():
            dest_dir = snapshot_dir / dirname
            _copy_item(dir_path, dest_dir)
            for sub_file in dest_dir.rglob("*"):
                if sub_file.is_file():
                    rel_path = sub_file.relative_to(snapshot_dir).as_posix()
                    size = sub_file.stat().st_size
                    sha256 = _hash_file(sub_file)
                    manifest_files[rel_path] = {"size": size, "sha256": sha256}
                    total_bytes += size

    # 3. Write manifest
    manifest_data = {
        "created_at": datetime.now().isoformat(),
        "source_data_dir": str(src_data_dir),
        "total_size_bytes": total_bytes,
        "files_count": len(manifest_files),
        "files": manifest_files,
    }

    manifest_path = snapshot_dir / MANIFEST_FILENAME
    manifest_path.write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8")

    return snapshot_dir


def list_snapshots(backup_dir: Path | str) -> list[dict[str, Any]]:
    """List all available snapshot recovery points in descending order by creation time.

    Args:
        backup_dir: Path to directory containing snapshots.

    Returns:
        List of dictionaries with snapshot metadata.
    """
    backup_path = Path(backup_dir)
    if not backup_path.exists() or not backup_path.is_dir():
        return []

    snapshots: list[dict[str, Any]] = []

    for entry in backup_path.iterdir():
        if not entry.is_dir() or entry.name.startswith("."):
            continue

        manifest_file = entry / MANIFEST_FILENAME
        if manifest_file.is_file():
            try:
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                snapshots.append({
                    "id": entry.name,
                    "path": entry,
                    "created_at": manifest.get("created_at", entry.name),
                    "files_count": manifest.get("files_count", 0),
                    "size_bytes": manifest.get("total_size_bytes", 0),
                    "manifest": manifest,
                })
                continue
            except (json.JSONDecodeError, OSError):
                pass

        # Fallback if no manifest exists: calculate on the fly
        files_count = 0
        size_bytes = 0
        for f in entry.rglob("*"):
            if f.is_file():
                files_count += 1
                size_bytes += f.stat().st_size

        mtime = datetime.fromtimestamp(entry.stat().st_mtime).isoformat()
        snapshots.append({
            "id": entry.name,
            "path": entry,
            "created_at": mtime,
            "files_count": files_count,
            "size_bytes": size_bytes,
            "manifest": None,
        })

    # Sort descending (most recent first)
    snapshots.sort(key=lambda s: s["created_at"], reverse=True)
    return snapshots


def restore_snapshot(snapshot_path: Path | str, target_data_dir: Path | str) -> bool:
    """Safely restore a snapshot to the target data directory with integrity checking.

    Args:
        snapshot_path: Path to snapshot directory.
        target_data_dir: Destination Antigravity data directory.

    Returns:
        True if snapshot was successfully verified and restored, False otherwise.
    """
    src_snapshot = Path(snapshot_path)
    dest_dir = Path(target_data_dir)

    if not src_snapshot.exists() or not src_snapshot.is_dir():
        logger.error("Snapshot path does not exist: %s", src_snapshot)
        return False

    manifest_file = src_snapshot / MANIFEST_FILENAME

    # 1. Integrity check against manifest if present
    if manifest_file.is_file():
        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            expected_files: dict[str, dict[str, Any]] = manifest.get("files", {})
            for rel_path, meta in expected_files.items():
                file_in_snap = src_snapshot / rel_path
                if not file_in_snap.is_file():
                    logger.error("Integrity check failed: missing file %s in snapshot", rel_path)
                    return False
                if meta.get("size") is not None and file_in_snap.stat().st_size != meta["size"]:
                    logger.error("Integrity check failed: size mismatch for %s", rel_path)
                    return False
                if meta.get("sha256") and _hash_file(file_in_snap) != meta["sha256"]:
                    logger.error("Integrity check failed: hash mismatch for %s", rel_path)
                    return False
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to read snapshot manifest: %s", e)
            return False

    dest_dir.mkdir(parents=True, exist_ok=True)

    # 2. Restore individual files
    for filename in TARGET_FILES:
        src_file = src_snapshot / filename
        if src_file.is_file():
            dst_file = dest_dir / filename
            _copy_item(src_file, dst_file)

    # 3. Restore directories
    for dirname in TARGET_DIRS:
        src_subdir = src_snapshot / dirname
        if src_subdir.is_dir():
            dst_subdir = dest_dir / dirname
            dst_subdir.mkdir(parents=True, exist_ok=True)
            _copy_item(src_subdir, dst_subdir)

    return True


class BackupManager:
    """High-level orchestrator for Antigravity backups and recovery points."""

    def __init__(
        self,
        path_manager: PathManager | None = None,
        data_dir: Path | str | None = None,
        backup_dir: Path | str | None = None,
    ) -> None:
        if path_manager is not None:
            self._data_dir = path_manager.data_dir
            self._backup_dir = Path(backup_dir) if backup_dir is not None else path_manager.backups_dir
        elif data_dir is not None:
            self._data_dir = Path(data_dir)
            self._backup_dir = Path(backup_dir) if backup_dir is not None else self._data_dir / ".backups"
        else:
            from antigravity_migrator.paths import PathManager

            pm = PathManager()
            self._data_dir = pm.data_dir
            self._backup_dir = Path(backup_dir) if backup_dir is not None else pm.backups_dir

    @property
    def data_dir(self) -> Path:
        """Root data directory being managed."""
        return self._data_dir

    @property
    def backup_dir(self) -> Path:
        """Directory where backups are stored."""
        return self._backup_dir

    def create_snapshot(self, backup_dir: Path | str | None = None) -> Path:
        """Create a point-in-time snapshot of the data directory."""
        target_dir = Path(backup_dir) if backup_dir is not None else self._backup_dir
        return create_snapshot(self._data_dir, backup_dir=target_dir)

    def list_snapshots(self, backup_dir: Path | str | None = None) -> list[dict[str, Any]]:
        """List available snapshots in descending order."""
        target_dir = Path(backup_dir) if backup_dir is not None else self._backup_dir
        return list_snapshots(target_dir)

    def restore_snapshot(
        self,
        snapshot_path: Path | str,
        target_data_dir: Path | str | None = None,
    ) -> bool:
        """Restore a snapshot to target_data_dir or default data_dir."""
        target = Path(target_data_dir) if target_data_dir is not None else self._data_dir
        return restore_snapshot(snapshot_path, target)
