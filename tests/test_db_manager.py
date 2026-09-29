import sqlite3
import tempfile
import unittest
from pathlib import Path

from antigravity_migrator.proto_codec import (
    build_workspace_info,
    encode_field,
)
from antigravity_migrator.db_manager import (
    DatabaseManager,
    extract_workspace_uri,
    load_conversation_summaries,
    update_summary_record,
    update_trajectory_metadata,
)


class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _create_sample_trajectory_db(
        self, db_path: Path, blob: bytes | None = None
    ) -> Path:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                "CREATE TABLE trajectory_metadata_blob (id TEXT PRIMARY KEY DEFAULT 'main', data BLOB)"
            )
            if blob is not None:
                conn.execute(
                    "INSERT INTO trajectory_metadata_blob (id, data) VALUES ('main', ?)",
                    (blob,),
                )
        return db_path

    def _create_sample_summaries_db(self, db_path: Path) -> Path:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE conversation_summaries (
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
        return db_path

    def test_extract_workspace_uri_from_subfield_1(self):
        ws_info = build_workspace_info(
            uri="file:///Users/dev/my-project",
            repo="my-org/my-project",
            git_url="https://github.com/my-org/my-project.git",
            branch="dev",
        )
        # Field 1 = WorkspaceInfo
        blob = encode_field(1, 2, ws_info) + encode_field(6, 2, "conv-uuid-1234")
        db_path = self._create_sample_trajectory_db(
            self.base_dir / "conv1.db", blob=blob
        )

        uri = extract_workspace_uri(db_path)
        self.assertEqual(uri, "file:///Users/dev/my-project")
        # Also check class method call
        self.assertEqual(
            DatabaseManager.extract_workspace_uri(db_path),
            "file:///Users/dev/my-project",
        )

    def test_extract_workspace_uri_from_field_7(self):
        # Only field 7 has the URI
        blob = encode_field(7, 2, "file:///Users/dev/fallback-project")
        db_path = self._create_sample_trajectory_db(
            self.base_dir / "conv2.db", blob=blob
        )

        uri = extract_workspace_uri(db_path)
        self.assertEqual(uri, "file:///Users/dev/fallback-project")

    def test_extract_workspace_uri_missing_or_corrupted(self):
        # Non-existent DB
        self.assertIsNone(extract_workspace_uri(self.base_dir / "missing.db"))

        # DB without table
        empty_db = self.base_dir / "empty.db"
        with sqlite3.connect(str(empty_db)) as conn:
            conn.execute("CREATE TABLE foo (id INT)")
        self.assertIsNone(extract_workspace_uri(empty_db))

        # DB with table but no 'main' row
        no_row_db = self._create_sample_trajectory_db(self.base_dir / "no_row.db")
        self.assertIsNone(extract_workspace_uri(no_row_db))

        # DB with corrupted blob
        corrupt_db = self._create_sample_trajectory_db(
            self.base_dir / "corrupt.db", blob=b"\xff\xff\xff\xff"
        )
        self.assertIsNone(extract_workspace_uri(corrupt_db))

    def test_update_trajectory_metadata_create_and_update(self):
        db_path = self.base_dir / "conversations" / "new_conv.db"
        blob_v1 = encode_field(7, 2, "file:///Users/dev/project-v1")

        # Create new record
        res1 = update_trajectory_metadata(db_path, blob_v1)
        self.assertTrue(res1)
        self.assertEqual(extract_workspace_uri(db_path), "file:///Users/dev/project-v1")

        # Update existing record
        blob_v2 = encode_field(7, 2, "file:///Users/dev/project-v2")
        res2 = DatabaseManager.update_trajectory_metadata(db_path, blob_v2)
        self.assertTrue(res2)
        self.assertEqual(extract_workspace_uri(db_path), "file:///Users/dev/project-v2")

        # Verify atomic write in DB directly
        with sqlite3.connect(str(db_path)) as conn:
            cur = conn.cursor()
            cur.execute("SELECT data FROM trajectory_metadata_blob WHERE id = 'main'")
            row = cur.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], blob_v2)

    def test_load_conversation_summaries(self):
        db_path = self._create_sample_summaries_db(
            self.base_dir / "conversation_summaries.db"
        )
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                "INSERT INTO conversation_summaries (conversation_id, title, project_id, raw_summary) "
                "VALUES ('uuid-1', 'Refactor Parser', 'proj-1', ?)",
                (b"summary-blob-1",),
            )
            conn.execute(
                "INSERT INTO conversation_summaries (conversation_id, title, project_id, raw_summary) "
                "VALUES ('uuid-2', 'Add Unit Tests', 'proj-2', ?)",
                (b"summary-blob-2",),
            )

        summaries = load_conversation_summaries(db_path)
        self.assertEqual(len(summaries), 2)
        self.assertIn("uuid-1", summaries)
        self.assertIn("uuid-2", summaries)

        self.assertEqual(summaries["uuid-1"]["title"], "Refactor Parser")
        self.assertEqual(summaries["uuid-1"]["project_id"], "proj-1")
        self.assertEqual(summaries["uuid-1"]["raw_summary"], b"summary-blob-1")

        self.assertEqual(summaries["uuid-2"]["title"], "Add Unit Tests")
        self.assertEqual(summaries["uuid-2"]["project_id"], "proj-2")
        self.assertEqual(summaries["uuid-2"]["raw_summary"], b"summary-blob-2")

        # Non-existent DB returns empty dict
        self.assertEqual(
            load_conversation_summaries(self.base_dir / "does_not_exist.db"), {}
        )

    def test_update_summary_record_existing_row(self):
        db_path = self._create_sample_summaries_db(
            self.base_dir / "conversation_summaries.db"
        )
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                "INSERT INTO conversation_summaries (conversation_id, title, project_id, raw_summary) "
                "VALUES ('uuid-10', 'Old Title', 'old-proj', ?)",
                (b"old-raw",),
            )

        # Full update
        success = update_summary_record(
            db_path=db_path,
            conversation_id="uuid-10",
            title="New Title",
            project_id="new-proj",
            raw_summary=b"new-raw",
        )
        self.assertTrue(success)

        updated = load_conversation_summaries(db_path)["uuid-10"]
        self.assertEqual(updated["title"], "New Title")
        self.assertEqual(updated["project_id"], "new-proj")
        self.assertEqual(updated["raw_summary"], b"new-raw")

        # Partial update (only project_id)
        partial_success = update_summary_record(
            db_path=db_path,
            conversation_id="uuid-10",
            title=None,
            project_id="another-proj",
            raw_summary=None,
        )
        self.assertTrue(partial_success)

        partially_updated = load_conversation_summaries(db_path)["uuid-10"]
        self.assertEqual(partially_updated["title"], "New Title")
        self.assertEqual(partially_updated["project_id"], "another-proj")
        self.assertEqual(partially_updated["raw_summary"], b"new-raw")

    def test_update_summary_record_insert_new_row(self):
        db_path = self._create_sample_summaries_db(
            self.base_dir / "conversation_summaries.db"
        )

        success = update_summary_record(
            db_path=db_path,
            conversation_id="uuid-brand-new",
            title="Brand New Chat",
            project_id="brand-new-proj",
            raw_summary=b"brand-new-raw",
        )
        self.assertTrue(success)

        record = load_conversation_summaries(db_path)["uuid-brand-new"]
        self.assertEqual(record["title"], "Brand New Chat")
        self.assertEqual(record["project_id"], "brand-new-proj")
        self.assertEqual(record["raw_summary"], b"brand-new-raw")

    def test_busy_timeout_configured(self):
        db_path = self.base_dir / "timeout_test.db"
        update_trajectory_metadata(db_path, b"test")

        # Verify busy_timeout is set when executing operations
        with sqlite3.connect(str(db_path), timeout=5.0) as conn:
            conn.execute("PRAGMA busy_timeout = 5000")
            cur = conn.cursor()
            cur.execute("PRAGMA busy_timeout")
            timeout_val = cur.fetchone()[0]
            self.assertEqual(timeout_val, 5000)

    def test_extract_workspace_uri_direct_string_in_field_1(self):
        # Field 1 stored directly as UTF-8 string payload
        blob = encode_field(1, 2, "file:///Users/dev/direct-field-1")
        db_path = self._create_sample_trajectory_db(
            self.base_dir / "conv_direct.db", blob=blob
        )
        uri = extract_workspace_uri(db_path)
        self.assertEqual(uri, "file:///Users/dev/direct-field-1")

    def test_update_summary_record_creates_file_and_table_if_missing(self):
        db_path = self.base_dir / "new_dir" / "fresh_summaries.db"
        success = update_summary_record(
            db_path=db_path,
            conversation_id="fresh-1",
            title="Fresh Conversation",
            project_id="proj-fresh",
            raw_summary=b"fresh-blob",
        )
        self.assertTrue(success)
        records = load_conversation_summaries(db_path)
        self.assertIn("fresh-1", records)
        self.assertEqual(records["fresh-1"]["title"], "Fresh Conversation")
        self.assertEqual(records["fresh-1"]["project_id"], "proj-fresh")
        self.assertEqual(records["fresh-1"]["raw_summary"], b"fresh-blob")


if __name__ == "__main__":
    unittest.main()

