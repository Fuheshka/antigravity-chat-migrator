"""Tests for pure Python Protobuf codec for Antigravity metadata."""

import unittest
from antigravity_migrator.proto_codec import (
    encode_varint,
    encode_field,
    parse_proto,
    build_workspace_info,
    inject_project_id_into_metadata,
)


class TestProtoCodec(unittest.TestCase):
    def test_encode_varint_basic(self):
        self.assertEqual(encode_varint(0), b"\x00")
        self.assertEqual(encode_varint(1), b"\x01")
        self.assertEqual(encode_varint(127), b"\x7f")
        self.assertEqual(encode_varint(128), b"\x80\x01")
        self.assertEqual(encode_varint(300), b"\xac\x02")

    def test_encode_varint_negative(self):
        # Protobuf encodes negative 64-bit varints as 10 bytes (two's complement)
        encoded = encode_varint(-1)
        self.assertEqual(len(encoded), 10)
        self.assertEqual(encoded, b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\x01")

    def test_encode_field_wire_types(self):
        # Wire type 0 (varint)
        field_0 = encode_field(1, 0, 150)
        self.assertEqual(field_0, b"\x08\x96\x01")

        # Wire type 2 (length-delimited)
        field_2 = encode_field(2, 2, b"hello")
        self.assertEqual(field_2, b"\x12\x05hello")

        # Wire type 1 (64-bit fixed)
        payload_8 = b"\x01\x02\x03\x04\x05\x06\x07\x08"
        field_1 = encode_field(3, 1, payload_8)
        self.assertEqual(field_1, b"\x19" + payload_8)

        # Wire type 5 (32-bit fixed)
        payload_4 = b"\x0a\x0b\x0c\x0d"
        field_5 = encode_field(4, 5, payload_4)
        self.assertEqual(field_5, b"\x25" + payload_4)

        # Unsupported wire type raises ValueError
        with self.assertRaises(ValueError):
            encode_field(1, 3, b"invalid")

    def test_parse_proto_valid(self):
        data = (
            encode_field(1, 0, 42)
            + encode_field(2, 2, b"antigravity")
            + encode_field(3, 1, b"12345678")
            + encode_field(4, 5, b"1234")
        )
        parsed = parse_proto(data)
        self.assertEqual(len(parsed), 4)
        self.assertEqual(parsed[0], (1, 0, 42))
        self.assertEqual(parsed[1], (2, 2, b"antigravity"))
        self.assertEqual(parsed[2], (3, 1, b"12345678"))
        self.assertEqual(parsed[3], (4, 5, b"1234"))

    def test_parse_proto_empty_and_corrupted(self):
        self.assertEqual(parse_proto(b""), [])
        self.assertEqual(parse_proto(None), [])
        
        # Corrupted tag varint (infinite continuation bit without termination)
        self.assertEqual(parse_proto(b"\x80\x80\x80"), [])

        # Truncated varint value
        self.assertEqual(parse_proto(b"\x08\x80"), [])

        # Truncated length-delimited payload (claims 100 bytes, only 3 provided)
        self.assertEqual(parse_proto(b"\x12\x64abc"), [])

        # Truncated fixed 64-bit and 32-bit
        self.assertEqual(parse_proto(b"\x19\x01\x02"), [])
        self.assertEqual(parse_proto(b"\x25\x01"), [])

        # Partial valid stream followed by corruption: should salvage valid parsed fields
        valid_part = encode_field(1, 0, 99)
        corrupted_stream = valid_part + b"\x12\x64incomplete"
        parsed = parse_proto(corrupted_stream)
        self.assertEqual(parsed, [(1, 0, 99)])

    def test_build_workspace_info_without_git(self):
        uri = "file:///Users/testuser/project"
        ws_info = build_workspace_info(uri)
        parsed = parse_proto(ws_info)
        
        field_map = {fn: val for fn, wt, val in parsed}
        self.assertEqual(field_map[1], uri.encode("utf-8"))
        self.assertEqual(field_map[2], uri.encode("utf-8"))
        self.assertEqual(field_map[3], b"")

    def test_build_workspace_info_with_git(self):
        uri = "file:///Users/testuser/project"
        repo = "owner/repo"
        git_url = "https://github.com/owner/repo.git"
        branch = "feature/test"
        
        ws_info = build_workspace_info(uri, repo=repo, git_url=git_url, branch=branch)
        parsed = parse_proto(ws_info)
        field_map = {fn: val for fn, wt, val in parsed}
        
        self.assertEqual(field_map[1], uri.encode("utf-8"))
        self.assertEqual(field_map[2], uri.encode("utf-8"))
        self.assertEqual(field_map[4], branch.encode("utf-8"))

        git_meta_parsed = parse_proto(field_map[3])
        git_map = {fn: val for fn, wt, val in git_meta_parsed}
        self.assertEqual(git_map[1], repo.encode("utf-8"))
        self.assertEqual(git_map[2], git_url.encode("utf-8"))

    def test_build_workspace_info_empty_or_none(self):
        self.assertEqual(build_workspace_info(""), b"")
        self.assertEqual(build_workspace_info(None), b"")

    def test_inject_project_id_into_metadata_new_and_override(self):
        # 1. Starting with empty metadata
        meta = inject_project_id_into_metadata(b"", "proj-123")
        fields = parse_proto(meta)
        field_map = {fn: val for fn, wt, val in fields}
        self.assertEqual(field_map[18], b"proj-123")

        # 2. Replacing existing project_id (field 18)
        new_meta = inject_project_id_into_metadata(meta, "proj-456")
        fields = parse_proto(new_meta)
        # Should not duplicate field 18
        pids = [val for fn, wt, val in fields if fn == 18]
        self.assertEqual(pids, [b"proj-456"])

    def test_inject_project_id_with_new_workspace_info(self):
        ws_info = build_workspace_info("file:///Users/testuser/repo")
        existing_meta = encode_field(1, 2, b"old-ws") + encode_field(6, 2, b"conv-uuid-1")
        
        updated_meta = inject_project_id_into_metadata(
            existing_meta,
            project_id="proj-new",
            new_ws_info=ws_info,
        )
        fields = parse_proto(updated_meta)
        field_map = {fn: val for fn, wt, val in fields}
        
        self.assertEqual(field_map[1], ws_info)
        self.assertEqual(field_map[6], b"conv-uuid-1")
        self.assertEqual(field_map[18], b"proj-new")

    def test_inject_project_id_corrupted_metadata_safe(self):
        # Corrupted input should not raise exception and should produce valid proto with project_id
        res = inject_project_id_into_metadata(b"\xff\xff\x00\x12truncated", "proj-recovered")
        fields = parse_proto(res)
        field_map = {fn: val for fn, wt, val in fields}
        self.assertEqual(field_map[18], b"proj-recovered")

    def test_round_trip_field_17_and_18_antigravity_summary(self):
        # Simulate a CascadeTrajectorySummary containing:
        # Field 1: Last user message preview
        # Field 17: TrajectoryMetadata (which contains field 1 ws_info, field 6 cid, field 18 project_id)
        
        orig_ws = build_workspace_info("file:///Users/testuser/old-project")
        orig_traj_meta = (
            encode_field(1, 2, orig_ws)
            + encode_field(6, 2, b"chat-uuid-abc")
            + encode_field(18, 2, b"old-project-id")
        )
        
        orig_summary = (
            encode_field(1, 2, b"How do I fix Protobuf in Antigravity?")
            + encode_field(17, 2, orig_traj_meta)
        )

        # 1. Parse top summary
        summary_fields = parse_proto(orig_summary)
        new_summary_fields = []
        new_ws = build_workspace_info("file:///Users/testuser/new-project")
        
        for fn, wt, val in summary_fields:
            if fn == 17:
                # Modify nested TrajectoryMetadata
                modified_meta = inject_project_id_into_metadata(
                    val,
                    project_id="new-project-id",
                    new_ws_info=new_ws,
                )
                new_summary_fields.append(encode_field(fn, wt, modified_meta))
            else:
                new_summary_fields.append(encode_field(fn, wt, val))

        rebuilt_summary = b"".join(new_summary_fields)

        # 2. Verify round trip
        parsed_rebuilt = parse_proto(rebuilt_summary)
        summary_dict = {fn: val for fn, wt, val in parsed_rebuilt}
        
        self.assertEqual(summary_dict[1], b"How do I fix Protobuf in Antigravity?")
        
        # Verify subfields of Field 17
        traj_fields = parse_proto(summary_dict[17])
        traj_dict = {fn: val for fn, wt, val in traj_fields}
        
        self.assertEqual(traj_dict[6], b"chat-uuid-abc")
        self.assertEqual(traj_dict[18], b"new-project-id")
        self.assertEqual(traj_dict[1], new_ws)


if __name__ == "__main__":
    unittest.main()
