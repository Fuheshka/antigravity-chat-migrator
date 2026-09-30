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


def test_run_audit_corrupted_databases(mock_path_manager: PathManager):
    """Test run_audit gracefully handles 0-byte, invalid binary, and schema-corrupted databases."""
    import sqlite3

    conv_dir = mock_path_manager.conversations_dir

    # 1. 0-byte database file
    (conv_dir / "zero_byte.db").touch()

    # 2. Corrupted file with random binary garbage
    (conv_dir / "corrupted_binary.db").write_bytes(b"\x00\xff\xfe\xca\xfe\xba\xbeNOT_SQLITE_HEADER")

    # 3. Valid SQLite database with completely different / missing tables
    wrong_db = conv_dir / "wrong_schema.db"
    with sqlite3.connect(str(wrong_db)) as conn:
        conn.execute("CREATE TABLE dummy (key TEXT, val TEXT)")
        conn.execute("INSERT INTO dummy VALUES ('foo', 'bar')")

    # 4. Corrupted conversation_summaries.db
    mock_path_manager.summaries_db.write_bytes(b"CORRUPTED_SUMMARIES_BLOB")

    mock_watcher = MagicMock()
    mock_watcher.is_running.return_value = False
    mock_watcher.get_pids.return_value = []

    api = GuiBridgeApi(path_manager=mock_path_manager, process_watcher=mock_watcher)
    audit = api.run_audit()

    assert isinstance(audit, dict)
    assert audit["total_conversations"] == 3
    assert len(audit["conversations"]) == 3

    # All corrupted files should be safely mapped to outside_of_project with fallback titles
    for conv in audit["conversations"]:
        assert conv["status"] == "outside_of_project"
        assert conv["title"] == "Untitled Conversation"
        assert conv["project_id"] is None
        assert conv["workspace_uri"] is None

    # Verify JSON serialization succeeds without errors
    serialized = json.dumps(audit)
    assert len(serialized) > 0


def test_run_audit_inaccessible_and_missing_directories(mock_path_manager: PathManager):
    """Test run_audit and helpers when directories are missing or raise OS errors."""
    import shutil

    # 1. projects_dir missing
    shutil.rmtree(mock_path_manager.projects_dir)
    api = GuiBridgeApi(path_manager=mock_path_manager)
    assert api._load_project_names() == {}

    # 2. projects_dir with invalid JSON
    mock_path_manager.projects_dir.mkdir(parents=True, exist_ok=True)
    (mock_path_manager.projects_dir / "bad.json").write_text("{malformed: json", encoding="utf-8")
    (mock_path_manager.projects_dir / "valid.json").write_text(
        json.dumps({"id": "p1", "name": "Valid Project"}), encoding="utf-8"
    )
    names = api._load_project_names()
    assert names == {"p1": "Valid Project"}

    # 3. conversations_dir missing
    shutil.rmtree(mock_path_manager.conversations_dir)
    assert api._extract_conversations_details() == []

    # 4. Exception raised during audit
    with patch.object(api.service, "audit", side_effect=PermissionError("Permission denied")):
        result = api.run_audit()
        assert isinstance(result, dict)
        assert result["total_conversations"] == 0
        assert "error" in result
        assert json.dumps(result)


def test_run_fix_dry_run_vs_live_filesystem_verification(mock_path_manager: PathManager):
    """Verify that dry_run=True leaves disk completely untouched while dry_run=False persists changes."""
    import sqlite3
    from antigravity_migrator.proto_codec import build_workspace_info, encode_field

    ws_uri = "file:///Users/fuheshka/workspace/my-feature-repo"
    c_db = mock_path_manager.conversations_dir / "conv_test.db"

    # Create unbound database
    parts = [
        encode_field(1, 2, build_workspace_info(ws_uri)),
        encode_field(7, 2, ws_uri.encode("utf-8")),
    ]
    with sqlite3.connect(str(c_db)) as conn:
        conn.execute("CREATE TABLE trajectory_metadata_blob (id TEXT PRIMARY KEY, data BLOB)")
        conn.execute("INSERT INTO trajectory_metadata_blob VALUES ('main', ?)", (b"".join(parts),))

    initial_bytes = c_db.read_bytes()

    mock_watcher = MagicMock()
    mock_watcher.is_running.return_value = False
    mock_watcher.get_pids.return_value = []

    api = GuiBridgeApi(path_manager=mock_path_manager, process_watcher=mock_watcher)

    # 1. Simulation (Dry-Run)
    sim_res = api.run_fix(dry_run=True, auto_register=True)
    assert sim_res["success"] is True
    assert sim_res["dry_run"] is True
    assert sim_res["conversations_scanned"] == 1
    assert sim_res["conversations_updated"] == 1
    assert sim_res["backup_path"] is None or not Path(sim_res["backup_path"]).exists()

    # Verify database file remains 100% untouched
    assert c_db.read_bytes() == initial_bytes
    # Verify no snapshots created on disk
    assert len(list(mock_path_manager.backups_dir.glob("*"))) == 0
    # Verify no annotation file created
    assert not (mock_path_manager.annotations_dir / "conv_test.pbtxt").exists()

    # 2. Live Run (dry_run=False)
    live_res = api.run_fix(dry_run=False, auto_register=True)
    assert live_res["success"] is True
    assert live_res["dry_run"] is False
    assert live_res["conversations_updated"] == 1
    assert live_res["backup_path"] is not None
    assert Path(live_res["backup_path"]).exists()

    # Verify database file has changed
    assert c_db.read_bytes() != initial_bytes

    # Verify snapshot exists
    backups = api.list_backups()
    assert len(backups) == 1
    assert backups[0]["files_count"] > 0

    # Verify annotation was written
    ann_file = mock_path_manager.annotations_dir / "conv_test.pbtxt"
    assert ann_file.exists()


def test_list_backups_various_formats(mock_path_manager: PathManager):
    """Verify list_backups handles ISO strings, float timestamps, and date folder formats."""
    mock_bm = MagicMock()
    mock_bm.list_snapshots.return_value = [
        # Standard folder format
        {
            "id": "2026-09-30_12-30-45",
            "path": mock_path_manager.backups_dir / "2026-09-30_12-30-45",
            "created_at": None,
            "files_count": 10,
            "size_bytes": 2048,
        },
        # ISO string format
        {
            "id": "custom_snap_iso",
            "path": mock_path_manager.backups_dir / "custom_snap_iso",
            "created_at": "2026-09-30T14:15:00",
            "files_count": 5,
            "size_bytes": 1024,
        },
        # Numeric timestamp
        {
            "id": "custom_snap_num",
            "path": mock_path_manager.backups_dir / "custom_snap_num",
            "created_at": 1790757000.0,
            "files_count": 8,
            "size_bytes": 4096,
        },
        # Unparseable fallback
        {
            "id": "custom_unparseable",
            "path": mock_path_manager.backups_dir / "custom_unparseable",
            "created_at": "not-a-date",
            "files_count": 1,
            "size_bytes": 512,
        },
    ]

    api = GuiBridgeApi(path_manager=mock_path_manager, backup_manager=mock_bm)
    backups = api.list_backups()

    assert len(backups) == 4
    assert backups[0]["id"] == "2026-09-30_12-30-45"
    assert "2026-09-30 12:30:45" in backups[0]["date_formatted"]
    assert backups[1]["id"] == "custom_snap_iso"
    assert "2026-09-30 14:15:00" in backups[1]["date_formatted"]
    assert backups[2]["id"] == "custom_snap_num"
    assert backups[2]["timestamp"] == 1790757000.0
    assert backups[3]["id"] == "custom_unparseable"
    assert backups[3]["date_formatted"] == "not-a-date"

    assert json.dumps(backups)


def test_restore_backup_nonexistent_and_absolute_path(mock_path_manager: PathManager):
    """Verify restore_backup with non-existent snapshot and with absolute path."""
    mock_watcher = MagicMock()
    mock_watcher.is_running.return_value = False

    mock_bm = MagicMock()
    mock_bm.backup_dir = mock_path_manager.backups_dir
    mock_bm.restore_snapshot.return_value = False

    api = GuiBridgeApi(
        path_manager=mock_path_manager,
        process_watcher=mock_watcher,
        backup_manager=mock_bm,
    )

    # Failed restore
    res_fail = api.restore_backup("nonexistent_id")
    assert res_fail["success"] is False
    assert "Failed to restore" in res_fail["error"]

    # Absolute path restore
    abs_snap = mock_path_manager.backups_dir / "2026-09-30_99-99-99"
    abs_snap.mkdir(parents=True, exist_ok=True)
    mock_bm.restore_snapshot.return_value = True

    res_abs = api.restore_backup(str(abs_snap))
    assert res_abs["success"] is True
    assert res_abs["snapshot_id"] == str(abs_snap)


def test_api_strict_json_contract(mock_path_manager: PathManager):
    """Validate that every GuiBridgeApi response contains strictly JSON-serializable types and expected keys."""
    mock_watcher = MagicMock()
    mock_watcher.is_running.return_value = False
    mock_watcher.get_pids.return_value = []

    api = GuiBridgeApi(path_manager=mock_path_manager, process_watcher=mock_watcher)

    # 1. get_system_info
    sys_info = api.get_system_info()
    encoded = json.dumps(sys_info)
    decoded = json.loads(encoded)
    assert isinstance(decoded["paths"], dict)
    assert all(isinstance(k, str) and isinstance(v, str) for k, v in decoded["paths"].items())

    # 2. get_process_status
    proc_status = api.get_process_status()
    decoded = json.loads(json.dumps(proc_status))
    assert decoded["is_running"] is False
    assert isinstance(decoded["pids"], list)

    # 3. run_audit
    audit = api.run_audit()
    decoded = json.loads(json.dumps(audit))
    assert isinstance(decoded["unregistered_workspaces"], list)
    assert isinstance(decoded["conversations"], list)
    assert isinstance(decoded["total_conversations"], int)

    # 4. run_fix
    fix = api.run_fix(dry_run=True)
    decoded = json.loads(json.dumps(fix))
    assert isinstance(decoded["success"], bool)
    assert isinstance(decoded["errors"], list)

    # 5. list_backups
    backups = api.list_backups()
    decoded = json.loads(json.dumps(backups))
    assert isinstance(decoded, list)

    # 6. restore_backup
    restore = api.restore_backup("dummy_id")
    decoded = json.loads(json.dumps(restore))
    assert isinstance(decoded["success"], bool)
    assert "snapshot_id" in decoded


