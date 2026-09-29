"""Antigravity Chat Migrator & Project Sync Utility."""

from antigravity_migrator.paths import PathManager
from antigravity_migrator.proto_codec import (
    build_workspace_info,
    encode_field,
    encode_varint,
    inject_project_id_into_metadata,
    parse_proto,
)
from antigravity_migrator.db_manager import (
    DatabaseManager,
    extract_workspace_uri,
    load_conversation_summaries,
    update_summary_record,
    update_trajectory_metadata,
)
from antigravity_migrator.annotation_generator import (
    AnnotationGenerator,
    ensure_annotation_file,
    extract_title_from_transcript,
    generate_annotation_pbtxt,
)
from antigravity_migrator.project_registry import (
    ProjectRegistry,
    load_registered_projects,
    normalize_workspace_uri,
    register_new_project,
)

__version__ = "0.1.0"

__all__ = [
    "PathManager",
    "DatabaseManager",
    "extract_workspace_uri",
    "update_trajectory_metadata",
    "load_conversation_summaries",
    "update_summary_record",
    "parse_proto",
    "encode_varint",
    "encode_field",
    "build_workspace_info",
    "inject_project_id_into_metadata",
    "AnnotationGenerator",
    "extract_title_from_transcript",
    "generate_annotation_pbtxt",
    "ensure_annotation_file",
    "ProjectRegistry",
    "load_registered_projects",
    "normalize_workspace_uri",
    "register_new_project",
]

