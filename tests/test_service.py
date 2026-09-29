"""Tests for MigratorService (audit, sync, dry_run, protobuf and database synchronization)."""

import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

from antigravity_migrator.paths import PathManager
from antigravity_migrator.proto_codec import (
    build_workspace_info,
    encode_field,
    inject_project_id_into_metadata,
    parse_proto,
)
from antigravity_migrator.project_registry import register_new_project
from antigravity_migrator.service import (
    AuditReport,
    MigratorService,
    SyncResult,
)


def _create_mock_trajectory_db(
    db_path: Path,
    workspace_uri: str | None = None,
    project_id: str | None = None,
    cid: str | None = None,
) -> None:
    """Helper to create a synthetic conversation SQLite database."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    parts = []
    if workspace_uri:
        ws_info = build_workspace_info(workspace_uri)
        parts.append(encode_field(1, 2, ws_info))
        parts.append(encode_field(7, 2, workspace_uri.encode("utf-8")))
    if cid:
        parts.append(encode_field(6, 2, cid.encode("utf-8")))
    if project_id:
        parts.append(encode_field(18, 2, project_id.encode("utf-8")))

    blob = b"".join(parts)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS trajectory_metadata_blob (id TEXT PRIMARY KEY, data BLOB)"
        )
        conn.execute(
            "INSERT OR REPLACE INTO trajectory_metadata_blob (id, data) VALUES ('main', ?)",
            (blob,),
        )


def _create_mock_transcript(tr_path: Path, request_text: str) -> None:
    """Helper to create a synthetic transcript.jsonl file."""
    tr_path.parent.mkdir(parents=True, exist_ok=True)
    step1 = {
        "step_index": 0,
        "type": "USER_INPUT",
        "source": "USER_EXPLICIT",
        "created_at": "2026-09-29T12:00:00Z",
        "content": f"<USER_REQUEST>\n/goal /vibe-coding\n### 1. Цель\n{request_text}\n</USER_REQUEST>",
    }
    with open(tr_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(step1) + "\n")


class TestMigratorService(unittest.TestCase):
    """Test suite for MigratorService end-to-end operations."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="migrator_service_test_")
        self.root = Path(self.temp_dir)
        self.data_dir = self.root / "antigravity"
        self.config_dir = self.root / "config"

        self.pm = PathManager(data_dir=self.data_dir, config_dir=self.config_dir)
        self.pm.ensure_dirs()

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_audit_empty_environment(self) -> None:
        service = MigratorService(path_manager=self.pm)
        report = service.audit()

        self.assertIsInstance(report, AuditReport)
        self.assertEqual(report.total_conversations, 0)
        self.assertEqual(report.bound_to_projects, 0)
        self.assertEqual(report.outside_of_project, 0)
        self.assertEqual(report.missing_annotations, 0)
        self.assertEqual(report.unregistered_workspaces, [])

    def test_audit_synthetic_environment(self) -> None:
        # 1. Register a project in config
        reg_ws = "file:///Users/developer/project-alpha"
        proj_id_alpha = register_new_project(
            config_dir=self.pm.projects_dir,
            workspace_uri=reg_ws,
            project_name="Project Alpha",
        )

        # 2. Chat 1: Bound to Project Alpha (has field 18, has annotation)
        cid1 = "11111111-1111-1111-1111-111111111111"
        _create_mock_trajectory_db(
            self.pm.conversations_dir / f"{cid1}.db",
            workspace_uri=reg_ws,
            project_id=proj_id_alpha,
            cid=cid1,
        )
        (self.pm.annotations_dir / f"{cid1}.pbtxt").write_text(
            'title: "Chat 1"\nlast_user_view_time { seconds: 12345 nanos: 0 }\n',
            encoding="utf-8",
        )

        # 3. Chat 2: Outside of project, but workspace is known (no field 18, missing annotation)
        cid2 = "22222222-2222-2222-2222-222222222222"
        _create_mock_trajectory_db(
            self.pm.conversations_dir / f"{cid2}.db",
            workspace_uri=reg_ws,
            project_id=None,
            cid=cid2,
        )
        _create_mock_transcript(
            self.pm.brain_dir / cid2 / ".system_generated" / "logs" / "transcript.jsonl",
            "Реализация сервиса миграции",
        )

        # 4. Chat 3: Outside of project, and workspace is UNREGISTERED
        cid3 = "33333333-3333-3333-3333-333333333333"
        unreg_ws = "file:///Users/developer/project-beta"
        _create_mock_trajectory_db(
            self.pm.conversations_dir / f"{cid3}.db",
            workspace_uri=unreg_ws,
            project_id=None,
            cid=cid3,
        )
        _create_mock_transcript(
            self.pm.brain_dir / cid3 / ".system_generated" / "logs" / "transcript.jsonl",
            "Оптимизация производительности",
        )

        # 5. Chat 4: Explicit outside-of-project (no workspace, field 18 = "outside-of-project", has annotation)
        cid4 = "44444444-4444-4444-4444-444444444444"
        _create_mock_trajectory_db(
            self.pm.conversations_dir / f"{cid4}.db",
            workspace_uri=None,
            project_id="outside-of-project",
            cid=cid4,
        )
        (self.pm.annotations_dir / f"{cid4}.pbtxt").write_text(
            'title: "Global Question"\nlast_user_view_time { seconds: 54321 nanos: 0 }\n',
            encoding="utf-8",
        )

        service = MigratorService(path_manager=self.pm)
        report = service.audit()

        self.assertEqual(report.total_conversations, 4)
        self.assertEqual(report.bound_to_projects, 1)
        self.assertEqual(report.outside_of_project, 3)
        self.assertEqual(report.missing_annotations, 2)
        self.assertIn(unreg_ws, report.unregistered_workspaces)
        self.assertEqual(len(report.unregistered_workspaces), 1)

    def test_sync_dry_run_does_not_modify_disk(self) -> None:
        unreg_ws = "file:///Users/developer/project-gamma"
        cid = "55555555-5555-5555-5555-555555555555"
        db_file = self.pm.conversations_dir / f"{cid}.db"
        _create_mock_trajectory_db(db_file, workspace_uri=unreg_ws, project_id=None, cid=cid)
        _create_mock_transcript(
            self.pm.brain_dir / cid / ".system_generated" / "logs" / "transcript.jsonl",
            "Аудит базы данных",
        )

        service = MigratorService(path_manager=self.pm)
        result = service.sync(dry_run=True, auto_register=True)

        self.assertIsInstance(result, SyncResult)
        self.assertTrue(result.dry_run)
        self.assertTrue(result.success)
        self.assertIsNone(result.backup_path)
        self.assertEqual(result.conversations_scanned, 1)
        self.assertEqual(result.conversations_updated, 1)
        self.assertEqual(result.projects_registered, 1)
        self.assertEqual(result.annotations_created, 1)

        # Check disk: no projects created
        project_files = list(self.pm.projects_dir.glob("*.json"))
        self.assertEqual(len(project_files), 0)

        # Check disk: no annotation created
        ann_file = self.pm.annotations_dir / f"{cid}.pbtxt"
        self.assertFalse(ann_file.exists())

        # Check disk: db still has no project_id
        with sqlite3.connect(str(db_file)) as conn:
            cur = conn.cursor()
            cur.execute("SELECT data FROM trajectory_metadata_blob WHERE id = 'main'")
            row = cur.fetchone()
            fields = parse_proto(row[0])
            pids = [v for fn, wt, v in fields if fn == 18]
            self.assertEqual(pids, [])

    def test_sync_full_pipeline(self) -> None:
        reg_ws = "file:///Users/developer/existing-repo"
        existing_pid = register_new_project(
            config_dir=self.pm.projects_dir,
            workspace_uri=reg_ws,
            project_name="Existing Repo",
        )

        # Chat 1: in registered repo, but currently outside of project (no pid in db)
        cid1 = "aaaa1111-1111-1111-1111-111111111111"
        db1 = self.pm.conversations_dir / f"{cid1}.db"
        _create_mock_trajectory_db(db1, workspace_uri=reg_ws, project_id=None, cid=cid1)
        _create_mock_transcript(
            self.pm.brain_dir / cid1 / ".system_generated" / "logs" / "transcript.jsonl",
            "Интеграция с существующим репозиторием",
        )

        # Chat 2: in unregistered repo, needs auto-registration
        cid2 = "bbbb2222-2222-2222-2222-222222222222"
        new_ws = "file:///Users/developer/brand-new-project"
        db2 = self.pm.conversations_dir / f"{cid2}.db"
        _create_mock_trajectory_db(db2, workspace_uri=new_ws, project_id=None, cid=cid2)
        _create_mock_transcript(
            self.pm.brain_dir / cid2 / ".system_generated" / "logs" / "transcript.jsonl",
            "Разработка нового сервиса",
        )

        # Setup synthetic agyhub_summaries_proto.pb
        # Each entry has field 1 (cid) and field 2 (summary_bytes with field 17)
        orig_meta1 = encode_field(6, 2, cid1.encode("utf-8")) + encode_field(1, 2, build_workspace_info(reg_ws))
        orig_summary1 = encode_field(1, 2, b"Preview 1") + encode_field(17, 2, orig_meta1)
        entry1 = encode_field(1, 2, cid1.encode("utf-8")) + encode_field(2, 2, orig_summary1)

        orig_meta2 = encode_field(6, 2, cid2.encode("utf-8")) + encode_field(1, 2, build_workspace_info(new_ws))
        orig_summary2 = encode_field(1, 2, b"Preview 2") + encode_field(17, 2, orig_meta2)
        entry2 = encode_field(1, 2, cid2.encode("utf-8")) + encode_field(2, 2, orig_summary2)

        pb_content = encode_field(1, 2, entry1) + encode_field(1, 2, entry2)
        self.pm.summaries_pb.write_bytes(pb_content)

        # Run full sync
        service = MigratorService(path_manager=self.pm)
        result = service.sync(dry_run=False, auto_register=True)

        self.assertTrue(result.success)
        self.assertFalse(result.dry_run)
        self.assertIsNotNone(result.backup_path)
        self.assertTrue(result.backup_path.is_dir())
        self.assertTrue((result.backup_path / "manifest.json").is_file())
        self.assertEqual(result.conversations_scanned, 2)
        self.assertEqual(result.conversations_updated, 2)
        self.assertEqual(result.projects_registered, 1)
        self.assertEqual(result.annotations_created, 2)
        self.assertTrue(result.proto_cache_updated)
        self.assertTrue(result.summaries_db_updated)

        # Verify DB updates
        with sqlite3.connect(str(db1)) as conn:
            cur = conn.cursor()
            cur.execute("SELECT data FROM trajectory_metadata_blob WHERE id = 'main'")
            fields = parse_proto(cur.fetchone()[0])
            field_dict = {fn: val for fn, wt, val in fields}
            self.assertEqual(field_dict[18].decode("utf-8"), existing_pid)

        with sqlite3.connect(str(db2)) as conn:
            cur = conn.cursor()
            cur.execute("SELECT data FROM trajectory_metadata_blob WHERE id = 'main'")
            fields = parse_proto(cur.fetchone()[0])
            field_dict = {fn: val for fn, wt, val in fields}
            new_pid = field_dict[18].decode("utf-8")
            self.assertNotEqual(new_pid, "outside-of-project")

        # Verify annotations created on disk
        ann1 = self.pm.annotations_dir / f"{cid1}.pbtxt"
        ann2 = self.pm.annotations_dir / f"{cid2}.pbtxt"
        self.assertTrue(ann1.is_file())
        self.assertTrue(ann2.is_file())
        self.assertIn("Интеграция с существующим репозиторием", ann1.read_text(encoding="utf-8"))
        self.assertIn("Разработка нового сервиса", ann2.read_text(encoding="utf-8"))

        # Verify agyhub_summaries_proto.pb patched
        pb_parsed = parse_proto(self.pm.summaries_pb.read_bytes())
        found_cids = {}
        for fnum, wtype, entry_data in pb_parsed:
            if fnum == 1 and wtype == 2:
                efields = parse_proto(entry_data)
                ecid = None
                esummary = None
                for en, ewt, evalue in efields:
                    if en == 1:
                        ecid = evalue.decode("utf-8")
                    elif en == 2:
                        esummary = evalue
                if ecid and esummary:
                    sfields = parse_proto(esummary)
                    for sn, swt, sval in sfields:
                        if sn == 17:
                            tfields = parse_proto(sval)
                            tdict = {fn: val for fn, wt, val in tfields}
                            if 18 in tdict:
                                found_cids[ecid] = tdict[18].decode("utf-8")

        self.assertEqual(found_cids[cid1], existing_pid)
        self.assertEqual(found_cids[cid2], new_pid)

        # Verify conversation_summaries.db updated
        with sqlite3.connect(str(self.pm.summaries_db)) as conn:
            cur = conn.cursor()
            cur.execute("SELECT conversation_id, project_id, title FROM conversation_summaries")
            rows = dict((cid, (pid, title)) for cid, pid, title in cur.fetchall())
            self.assertEqual(rows[cid1][0], existing_pid)
            self.assertIn("Интеграция", rows[cid1][1])
            self.assertEqual(rows[cid2][0], new_pid)
            self.assertIn("Разработка", rows[cid2][1])

        # Verify audit after sync: 0 outside, 2 bound, 0 missing annotations, 0 unregistered
        report_after = service.audit()
        self.assertEqual(report_after.total_conversations, 2)
        self.assertEqual(report_after.bound_to_projects, 2)
        self.assertEqual(report_after.outside_of_project, 0)
        self.assertEqual(report_after.missing_annotations, 0)
        self.assertEqual(report_after.unregistered_workspaces, [])

    def test_sync_without_auto_register(self) -> None:
        unreg_ws = "file:///Users/developer/unregistered-standalone"
        cid = "cccc3333-3333-3333-3333-333333333333"
        db_file = self.pm.conversations_dir / f"{cid}.db"
        _create_mock_trajectory_db(db_file, workspace_uri=unreg_ws, project_id=None, cid=cid)

        service = MigratorService(path_manager=self.pm)
        result = service.sync(dry_run=False, auto_register=False)

        self.assertTrue(result.success)
        self.assertEqual(result.projects_registered, 0)

        # Database should have outside-of-project
        with sqlite3.connect(str(db_file)) as conn:
            cur = conn.cursor()
            cur.execute("SELECT data FROM trajectory_metadata_blob WHERE id = 'main'")
            fields = parse_proto(cur.fetchone()[0])
            field_dict = {fn: val for fn, wt, val in fields}
            self.assertEqual(field_dict[18].decode("utf-8"), "outside-of-project")

    def test_dataclasses_serialization(self) -> None:
        report = AuditReport(
            total_conversations=5,
            bound_to_projects=3,
            outside_of_project=2,
            missing_annotations=1,
            unregistered_workspaces=["file:///ws1", "file:///ws2"],
        )
        self.assertEqual(report.unregistered_count, 2)
        r_dict = report.to_dict()
        self.assertEqual(r_dict["total_conversations"], 5)
        self.assertEqual(len(r_dict["unregistered_workspaces"]), 2)

        res = SyncResult(
            success=True,
            dry_run=False,
            backup_path=Path("/tmp/backup"),
            conversations_scanned=2,
            conversations_updated=2,
            annotations_created=1,
            projects_registered=1,
            proto_cache_updated=True,
            summaries_db_updated=True,
            errors=[],
        )
        res_dict = res.to_dict()
        self.assertTrue(res_dict["success"])
        self.assertEqual(res_dict["backup_path"], "/tmp/backup")

    def test_constructor_with_string_paths(self) -> None:
        service = MigratorService(
            data_dir=str(self.data_dir),
            config_dir=str(self.config_dir),
        )
        self.assertEqual(service.path_manager.data_dir, self.data_dir)
        self.assertEqual(service.path_manager.config_dir, self.config_dir)


if __name__ == "__main__":
    unittest.main()

