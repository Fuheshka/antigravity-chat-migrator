"""Tests for BackupManager (atomic snapshots and rollback)."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path
import pytest

from antigravity_migrator.backup_manager import (
    BackupManager,
    create_snapshot,
    list_snapshots,
    restore_snapshot,
)
from antigravity_migrator.paths import PathManager


@pytest.fixture
def mock_data_env(tmp_path: Path):
    """Create a simulated Antigravity data directory with test files."""
    data_dir = tmp_path / "antigravity"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Key files
    pb_file = data_dir / "agyhub_summaries_proto.pb"
    pb_file.write_bytes(b"\x08\x01\x12\x04test\x1a\x06secret")

    db_file = data_dir / "conversation_summaries.db"
    db_file.write_bytes(b"SQLite format 3\x00mock-db-content")

    # Key directories
    annotations_dir = data_dir / "annotations"
    annotations_dir.mkdir()
    (annotations_dir / "chat-1.pbtxt").write_text("title: 'Chat 1'\n")
    (annotations_dir / "chat-2.pbtxt").write_text("title: 'Chat 2'\n")

    conversations_dir = data_dir / "conversations"
    conversations_dir.mkdir()
    (conversations_dir / "chat-1.db").write_bytes(b"chat-1-db-content")

    # Unrelated directory that should NOT be part of backup
    unrelated_dir = data_dir / "unrelated_cache"
    unrelated_dir.mkdir()
    (unrelated_dir / "temp.log").write_text("should not be backed up")

    return data_dir


def test_create_snapshot_default_location(mock_data_env: Path):
    """create_snapshot saves files in data_dir/.backups/<timestamp> by default."""
    snapshot_path = create_snapshot(mock_data_env)

    assert snapshot_path.exists()
    assert snapshot_path.is_dir()
    assert snapshot_path.parent == mock_data_env / ".backups"

    # Verify backed up items
    assert (snapshot_path / "agyhub_summaries_proto.pb").read_bytes() == b"\x08\x01\x12\x04test\x1a\x06secret"
    assert (snapshot_path / "conversation_summaries.db").read_bytes() == b"SQLite format 3\x00mock-db-content"
    assert (snapshot_path / "annotations" / "chat-1.pbtxt").read_text() == "title: 'Chat 1'\n"
    assert (snapshot_path / "annotations" / "chat-2.pbtxt").read_text() == "title: 'Chat 2'\n"
    assert (snapshot_path / "conversations" / "chat-1.db").read_bytes() == b"chat-1-db-content"

    # Verify unrelated items are excluded
    assert not (snapshot_path / "unrelated_cache").exists()

    # Verify manifest exists and is valid
    manifest_file = snapshot_path / "manifest.json"
    assert manifest_file.exists()
    manifest = json.loads(manifest_file.read_text())
    assert "created_at" in manifest
    assert "files" in manifest
    assert "agyhub_summaries_proto.pb" in manifest["files"]
    assert "conversation_summaries.db" in manifest["files"]
    assert "annotations/chat-1.pbtxt" in manifest["files"]


def test_create_snapshot_custom_backup_dir(mock_data_env: Path, tmp_path: Path):
    """create_snapshot respects a custom backup directory."""
    custom_backup_dir = tmp_path / "custom_backups"
    snapshot_path = create_snapshot(mock_data_env, backup_dir=custom_backup_dir)

    assert snapshot_path.exists()
    assert snapshot_path.parent == custom_backup_dir
    assert (snapshot_path / "agyhub_summaries_proto.pb").exists()


def test_create_snapshot_partial_files(tmp_path: Path):
    """create_snapshot gracefully handles folders where only some target files exist."""
    data_dir = tmp_path / "partial_data"
    data_dir.mkdir()
    (data_dir / "conversation_summaries.db").write_bytes(b"partial-db")

    snapshot_path = create_snapshot(data_dir)
    assert snapshot_path.exists()
    assert (snapshot_path / "conversation_summaries.db").read_bytes() == b"partial-db"
    assert not (snapshot_path / "agyhub_summaries_proto.pb").exists()
    assert not (snapshot_path / "annotations").exists()
    assert not (snapshot_path / "conversations").exists()


def test_create_snapshot_empty_dir(tmp_path: Path):
    """create_snapshot handles empty directory without error."""
    data_dir = tmp_path / "empty_data"
    data_dir.mkdir()

    snapshot_path = create_snapshot(data_dir)
    assert snapshot_path.exists()
    manifest_file = snapshot_path / "manifest.json"
    assert manifest_file.exists()
    manifest = json.loads(manifest_file.read_text())
    assert len(manifest["files"]) == 0


def test_list_snapshots(mock_data_env: Path, tmp_path: Path):
    """list_snapshots returns ordered metadata for available recovery points."""
    backup_dir = tmp_path / "backups_list_test"
    backup_dir.mkdir()

    # Initially empty
    assert list_snapshots(backup_dir) == []

    # Non-existent directory returns empty list
    assert list_snapshots(tmp_path / "non_existent") == []

    # Create first snapshot
    snap1 = create_snapshot(mock_data_env, backup_dir=backup_dir)
    time.sleep(1.05)  # Ensure distinct timestamp
    snap2 = create_snapshot(mock_data_env, backup_dir=backup_dir)

    snapshots = list_snapshots(backup_dir)
    assert len(snapshots) == 2
    # Most recent should be first
    assert snapshots[0]["id"] == snap2.name
    assert snapshots[1]["id"] == snap1.name
    assert snapshots[0]["files_count"] == 5  # 2 files + 2 annotations + 1 conversation
    assert snapshots[0]["size_bytes"] > 0
    assert snapshots[0]["path"] == snap2


def test_restore_snapshot_success(mock_data_env: Path, tmp_path: Path):
    """restore_snapshot safely restores data files from snapshot."""
    backup_dir = tmp_path / "backups"
    snapshot = create_snapshot(mock_data_env, backup_dir=backup_dir)

    # Mutate data_dir: delete a file, change another, add a corrupt file
    pb_file = mock_data_env / "agyhub_summaries_proto.pb"
    pb_file.unlink()
    db_file = mock_data_env / "conversation_summaries.db"
    db_file.write_bytes(b"corrupted-db")
    (mock_data_env / "annotations" / "chat-1.pbtxt").unlink()

    # Restore
    success = restore_snapshot(snapshot, mock_data_env)
    assert success is True

    # Check restored state
    assert pb_file.exists()
    assert pb_file.read_bytes() == b"\x08\x01\x12\x04test\x1a\x06secret"
    assert db_file.read_bytes() == b"SQLite format 3\x00mock-db-content"
    assert (mock_data_env / "annotations" / "chat-1.pbtxt").read_text() == "title: 'Chat 1'\n"


def test_restore_snapshot_integrity_failure(mock_data_env: Path, tmp_path: Path):
    """restore_snapshot fails and rejects restore if snapshot files are corrupted."""
    backup_dir = tmp_path / "backups"
    snapshot = create_snapshot(mock_data_env, backup_dir=backup_dir)

    # Tamper with snapshot file
    db_in_snapshot = snapshot / "conversation_summaries.db"
    db_in_snapshot.write_bytes(b"TAMPERED_DATA")

    # Restore should detect hash mismatch and return False
    target_dir = tmp_path / "restore_target"
    target_dir.mkdir()
    (target_dir / "conversation_summaries.db").write_bytes(b"original")

    success = restore_snapshot(snapshot, target_dir)
    assert success is False
    # Original file must remain untouched
    assert (target_dir / "conversation_summaries.db").read_bytes() == b"original"


def test_restore_snapshot_nonexistent(tmp_path: Path):
    """restore_snapshot returns False for missing snapshot path."""
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    success = restore_snapshot(tmp_path / "missing_snap", target_dir)
    assert success is False


def test_backup_manager_class(mock_data_env: Path, tmp_path: Path):
    """BackupManager high-level class orchestrates snapshots with PathManager."""
    pm = PathManager(data_dir=mock_data_env, config_dir=tmp_path / "config")
    manager = BackupManager(path_manager=pm)

    # Create snapshot via class
    snap_path = manager.create_snapshot()
    assert snap_path.exists()
    assert snap_path.parent == pm.backups_dir

    # List snapshots
    snaps = manager.list_snapshots()
    assert len(snaps) == 1
    assert snaps[0]["path"] == snap_path

    # Mutate data
    (mock_data_env / "agyhub_summaries_proto.pb").write_bytes(b"modified")

    # Restore via class
    ok = manager.restore_snapshot(snap_path)
    assert ok is True
    assert (mock_data_env / "agyhub_summaries_proto.pb").read_bytes() == b"\x08\x01\x12\x04test\x1a\x06secret"


def test_apfs_cow_fallback(mock_data_env: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify fallback to standard copy if APFS clonefile (cp -c) raises an exception."""
    import subprocess

    original_run = subprocess.run

    def mock_subprocess_run(cmd, *args, **kwargs):
        if isinstance(cmd, list) and cmd and cmd[0] == "cp":
            raise subprocess.CalledProcessError(1, cmd, stderr=b"cp: clonefile not supported")
        return original_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    # create_snapshot should still succeed using fallback
    custom_dir = tmp_path / "cow_fallback_backups"
    snapshot = create_snapshot(mock_data_env, backup_dir=custom_dir)
    assert snapshot.exists()
    assert (snapshot / "agyhub_summaries_proto.pb").exists()
