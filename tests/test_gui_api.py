"""Unit tests for GuiBridgeApi (pywebview JavaScript bridge adapter)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from antigravity_migrator.gui_api import GuiBridgeApi
from antigravity_migrator.paths import PathManager
from antigravity_migrator.service import AuditReport, MigratorService, SyncResult


@pytest.fixture
def mock_path_manager(tmp_path: Path) -> PathManager:
    """Fixture providing isolated temporary directories for PathManager."""
    data_dir = tmp_path / "antigravity"
    config_dir = tmp_path / "config"
    pm = PathManager(data_dir=data_dir, config_dir=config_dir)
    pm.ensure_dirs()
    return pm


def test_get_system_info(mock_path_manager: PathManager):
    """Test get_system_info returns OS, app version, language, and directory paths."""
    api = GuiBridgeApi(path_manager=mock_path_manager)
    info = api.get_system_info()

    assert isinstance(info, dict)
    assert "os" in info
    assert "app_version" in info
    assert "locale" in info
    assert info["locale"] in ("ru", "en")
    assert "paths" in info
    assert isinstance(info["paths"], dict)
    assert "data_dir" in info["paths"]
    assert "config_dir" in info["paths"]
    assert "conversations_dir" in info["paths"]
    assert "backups_dir" in info["paths"]

    # Verify JSON serializability
    json_str = json.dumps(info)
    assert len(json_str) > 0


def test_get_process_status_idle(mock_path_manager: PathManager):
    """Test get_process_status when Antigravity is not running."""
    mock_watcher = MagicMock()
    mock_watcher.is_running.return_value = False
    mock_watcher.get_pids.return_value = []

    api = GuiBridgeApi(path_manager=mock_path_manager, process_watcher=mock_watcher)
    status = api.get_process_status()

    assert isinstance(status, dict)
    assert status["is_running"] is False
    assert status["pids"] == []
    assert status.get("warning") is None or status.get("warning") == ""
    assert json.dumps(status)


def test_get_process_status_active(mock_path_manager: PathManager):
    """Test get_process_status when Antigravity processes are running."""
    mock_watcher = MagicMock()
    mock_watcher.is_running.return_value = True
    mock_watcher.get_pids.return_value = [1234, 5678]

    api = GuiBridgeApi(path_manager=mock_path_manager, process_watcher=mock_watcher)
    status = api.get_process_status()

    assert isinstance(status, dict)
    assert status["is_running"] is True
    assert status["pids"] == [1234, 5678]
    assert status.get("warning") is not None
    assert "1234" in status["warning"] or "5678" in status["warning"]
    assert json.dumps(status)


def test_run_audit_with_mock_service(mock_path_manager: PathManager):
    """Test run_audit returns summary metrics and dialog details."""
    mock_service = MagicMock()
    report = AuditReport(
        total_conversations=3,
        bound_to_projects=1,
        outside_of_project=2,
        missing_annotations=1,
        unregistered_workspaces=["file:///path/to/ws"],
    )
    mock_service.audit.return_value = report

    # Mock dialog extraction
    api = GuiBridgeApi(path_manager=mock_path_manager, service=mock_service)

    with patch.object(api, "_extract_conversations_details") as mock_details:
        mock_details.return_value = [
            {
                "id": "c1",
                "title": "Chat 1",
                "workspace_uri": "file:///path/to/ws",
                "project_id": "outside-of-project",
                "project_name": "Outside of Project",
                "status": "outside_of_project",
            },
            {
                "id": "c2",
                "title": "Chat 2",
                "workspace_uri": "file:///path/to/registered",
                "project_id": "proj-uuid-1",
                "project_name": "My Project",
                "status": "ok",
            },
        ]

        result = api.run_audit()

        assert isinstance(result, dict)
        assert result["total_conversations"] == 3
        assert result["bound_to_projects"] == 1
        assert result["outside_of_project"] == 2
        assert result["missing_annotations"] == 1
        assert result["unregistered_workspaces"] == ["file:///path/to/ws"]
        assert len(result["conversations"]) == 2
        assert result["conversations"][0]["id"] == "c1"
        assert result["conversations"][0]["status"] == "outside_of_project"
        assert result["conversations"][1]["id"] == "c2"
        assert result["conversations"][1]["status"] == "ok"
        assert json.dumps(result)


def test_run_fix_dry_run(mock_path_manager: PathManager):
    """Test run_fix in dry_run mode."""
    mock_service = MagicMock()
    sync_res = SyncResult(
        success=True,
        dry_run=True,
        conversations_scanned=5,
        conversations_updated=2,
        annotations_created=1,
        projects_registered=1,
    )
    mock_service.sync.return_value = sync_res

    api = GuiBridgeApi(path_manager=mock_path_manager, service=mock_service)
    res = api.run_fix(dry_run=True, auto_register=True)

    assert isinstance(res, dict)
    assert res["success"] is True
    assert res["dry_run"] is True
    assert res["conversations_scanned"] == 5
    assert res["conversations_updated"] == 2
    mock_service.sync.assert_called_once_with(dry_run=True, auto_register=True)
    assert json.dumps(res)


def test_run_fix_live(mock_path_manager: PathManager):
    """Test run_fix in live mode."""
    mock_service = MagicMock()
    sync_res = SyncResult(
        success=True,
        dry_run=False,
        backup_path=mock_path_manager.backups_dir / "snapshot-1",
        conversations_scanned=2,
        conversations_updated=2,
        annotations_created=0,
        projects_registered=1,
    )
    mock_service.sync.return_value = sync_res

    api = GuiBridgeApi(path_manager=mock_path_manager, service=mock_service)
    res = api.run_fix(dry_run=False, auto_register=True)

    assert isinstance(res, dict)
    assert res["success"] is True
    assert res["dry_run"] is False
    assert res["backup_path"] is not None
    assert json.dumps(res)


def test_list_backups(mock_path_manager: PathManager):
    """Test list_backups returns formatted snapshot items."""
    mock_bm = MagicMock()
    mock_bm.list_snapshots.return_value = [
        {
            "id": "2026-09-30_10-00-00",
            "path": mock_path_manager.backups_dir / "2026-09-30_10-00-00",
            "created_at": "2026-09-30T10:00:00",
            "files_count": 15,
            "size_bytes": 102400,
            "manifest": None,
        }
    ]

    api = GuiBridgeApi(path_manager=mock_path_manager, backup_manager=mock_bm)
    backups = api.list_backups()

    assert isinstance(backups, list)
    assert len(backups) == 1
    item = backups[0]
    assert item["id"] == "2026-09-30_10-00-00"
    assert "timestamp" in item
    assert "date_formatted" in item
    assert item["files_count"] == 15
    assert item["size_bytes"] == 102400
    assert json.dumps(backups)


def test_restore_backup_cold_disk_violation(mock_path_manager: PathManager):
    """Test restore_backup refuses to restore when Antigravity is running."""
    mock_watcher = MagicMock()
    mock_watcher.is_running.return_value = True

    mock_bm = MagicMock()

    api = GuiBridgeApi(
        path_manager=mock_path_manager,
        process_watcher=mock_watcher,
        backup_manager=mock_bm,
    )
    res = api.restore_backup("snapshot-123")

    assert isinstance(res, dict)
    assert res["success"] is False
    assert "cold_disk" in res.get("error", "").lower() or res.get("cold_disk_violation") is True
    mock_bm.restore_snapshot.assert_not_called()
    assert json.dumps(res)


def test_restore_backup_success(mock_path_manager: PathManager):
    """Test restore_backup successfully restores snapshot when IDE is closed."""
    mock_watcher = MagicMock()
    mock_watcher.is_running.return_value = False

    mock_bm = MagicMock()
    mock_bm.backup_dir = mock_path_manager.backups_dir
    mock_bm.restore_snapshot.return_value = True

    snap_dir = mock_path_manager.backups_dir / "snapshot-123"
    snap_dir.mkdir(parents=True, exist_ok=True)

    api = GuiBridgeApi(
        path_manager=mock_path_manager,
        process_watcher=mock_watcher,
        backup_manager=mock_bm,
    )
    res = api.restore_backup("snapshot-123")

    assert isinstance(res, dict)
    assert res["success"] is True
    assert res["snapshot_id"] == "snapshot-123"
    mock_bm.restore_snapshot.assert_called_once()
    assert json.dumps(res)


def test_exception_handling_safety(mock_path_manager: PathManager):
    """Test that all API methods safely handle unexpected exceptions without raising."""
    mock_service = MagicMock()
    mock_service.audit.side_effect = RuntimeError("Disk failure")
    mock_service.sync.side_effect = RuntimeError("Permission denied")

    mock_watcher = MagicMock()
    mock_watcher.get_pids.side_effect = RuntimeError("Process error")

    mock_bm = MagicMock()
    mock_bm.list_snapshots.side_effect = RuntimeError("Backup list error")
    mock_bm.restore_snapshot.side_effect = RuntimeError("Restore error")

    api = GuiBridgeApi(
        path_manager=mock_path_manager,
        service=mock_service,
        process_watcher=mock_watcher,
        backup_manager=mock_bm,
    )

    # get_process_status
    status = api.get_process_status()
    assert isinstance(status, dict)
    assert "error" in status or status.get("is_running") is False
    assert json.dumps(status)

    # run_audit
    audit = api.run_audit()
    assert isinstance(audit, dict)
    assert "error" in audit
    assert json.dumps(audit)

    # run_fix
    fix = api.run_fix()
    assert isinstance(fix, dict)
    assert fix["success"] is False
    assert "error" in fix or len(fix.get("errors", [])) > 0
    assert json.dumps(fix)

    # list_backups
    backups = api.list_backups()
    assert isinstance(backups, list)
    assert json.dumps(backups)

    # restore_backup
    mock_watcher.is_running.return_value = False
    restore = api.restore_backup("snapshot-fail")
    assert isinstance(restore, dict)
    assert restore["success"] is False
    assert "error" in restore
    assert json.dumps(restore)


def test_gui_api_real_filesystem_audit_and_fix(mock_path_manager: PathManager):
    """End-to-end integration test of GuiBridgeApi audit, sync, and restore on filesystem."""
    import sqlite3
    from antigravity_migrator.proto_codec import build_workspace_info, encode_field
    from antigravity_migrator.project_registry import register_new_project

    # 1. Register a project
    ws_uri = "file:///Users/fuheshka/workspace/repo-1"
    pid = register_new_project(
        config_dir=mock_path_manager.config_dir,
        workspace_uri=ws_uri,
        project_name="Repo One",
    )

    # 2. Create a bound conversation database
    c1_db = mock_path_manager.conversations_dir / "c1.db"
    parts1 = [
        encode_field(1, 2, build_workspace_info(ws_uri)),
        encode_field(7, 2, ws_uri.encode("utf-8")),
        encode_field(18, 2, pid.encode("utf-8")),
    ]
    with sqlite3.connect(str(c1_db)) as conn:
        conn.execute("CREATE TABLE trajectory_metadata_blob (id TEXT PRIMARY KEY, data BLOB)")
        conn.execute("INSERT INTO trajectory_metadata_blob VALUES ('main', ?)", (b"".join(parts1),))

    # Create annotation for c1
    c1_ann = mock_path_manager.annotations_dir / "c1.pbtxt"
    c1_ann.write_text('title: "Fix Authentication Flow"\n', encoding="utf-8")

    # 3. Create an unbound conversation database (outside-of-project) with unregistered workspace
    c2_db = mock_path_manager.conversations_dir / "c2.db"
    unreg_ws = "file:///Users/fuheshka/workspace/unregistered-repo"
    parts2 = [
        encode_field(1, 2, build_workspace_info(unreg_ws)),
        encode_field(7, 2, unreg_ws.encode("utf-8")),
    ]
    with sqlite3.connect(str(c2_db)) as conn:
        conn.execute("CREATE TABLE trajectory_metadata_blob (id TEXT PRIMARY KEY, data BLOB)")
        conn.execute("INSERT INTO trajectory_metadata_blob VALUES ('main', ?)", (b"".join(parts2),))

    # Mock process watcher as idle
    mock_watcher = MagicMock()
    mock_watcher.is_running.return_value = False
    mock_watcher.get_pids.return_value = []

    api = GuiBridgeApi(path_manager=mock_path_manager, process_watcher=mock_watcher)

    # Audit before fix
    audit_res = api.run_audit()
    assert audit_res["total_conversations"] == 2
    assert audit_res["bound_to_projects"] == 1
    assert audit_res["outside_of_project"] == 1
    assert audit_res["missing_annotations"] == 1
    assert len(audit_res["conversations"]) == 2

    c1_info = next(c for c in audit_res["conversations"] if c["id"] == "c1")
    assert c1_info["title"] == "Fix Authentication Flow"
    assert c1_info["project_name"] == "Repo One"
    assert c1_info["status"] == "ok"

    c2_info = next(c for c in audit_res["conversations"] if c["id"] == "c2")
    assert c2_info["status"] == "outside_of_project"

    # Run Fix
    fix_res = api.run_fix(dry_run=False, auto_register=True)
    assert fix_res["success"] is True
    assert fix_res["conversations_scanned"] == 2
    assert fix_res["projects_registered"] == 1

    # Verify backups listed
    backups = api.list_backups()
    assert len(backups) >= 1
    snap_id = backups[0]["id"]
    assert backups[0]["size_bytes"] > 0
    assert backups[0]["files_count"] > 0

    # Audit after fix
    audit_res2 = api.run_audit()
    assert audit_res2["bound_to_projects"] == 2
    assert audit_res2["outside_of_project"] == 0

    # Test Restore Backup
    restore_res = api.restore_backup(snap_id)
    assert restore_res["success"] is True
    assert restore_res["snapshot_id"] == snap_id

