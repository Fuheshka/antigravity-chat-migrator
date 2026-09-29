"""Project registry management for Antigravity workspaces and configurations."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from urllib.parse import unquote

from antigravity_migrator.paths import PathManager


def normalize_workspace_uri(raw_uri: str) -> str:
    """Normalize a local path or file URI into a canonical Antigravity workspace URI (file:///...)."""
    if not raw_uri:
        return ""

    raw = str(raw_uri).strip()
    clean = raw.replace("\\", "/")

    if clean.startswith("file:"):
        sub = clean[5:].lstrip("/")
        # Check for Windows drive letter like C:/... or c:/...
        if len(sub) >= 2 and sub[1] == ":" and sub[0].isalpha():
            drive = sub[0].upper()
            rest = sub[2:]
            path_part = f"{drive}:{rest}"
        else:
            path_part = sub
        canonical = f"file:///{path_part}"
    else:
        # Check for Windows drive letter like C:/... or c:/...
        if len(clean) >= 2 and clean[1] == ":" and clean[0].isalpha():
            drive = clean[0].upper()
            rest = clean[2:]
            canonical = f"file:///{drive}:{rest}"
        elif clean.startswith("/"):
            canonical = f"file://{clean}"
        else:
            canonical = f"file:///{clean}"

    # Strip trailing slashes, preserving root file:///
    if len(canonical) > 8 and canonical.endswith("/"):
        canonical = canonical.rstrip("/")

    return canonical


def _uri_to_path(uri: str) -> Path:
    """Convert a file URI to a local Path for filesystem inspection."""
    if uri.startswith("file://"):
        path_part = uri[7:]
        # On Windows-style URI (e.g. /C:/...)
        if len(path_part) >= 3 and path_part[0] == "/" and path_part[2] == ":":
            path_part = path_part[1:]
        return Path(unquote(path_part))
    return Path(unquote(uri))


def _resolve_load_dir(config_or_projects_dir: Path | str) -> Path:
    """Resolve directory to read project descriptors from."""
    p = Path(config_or_projects_dir)
    if (p / "projects").is_dir():
        return p / "projects"
    return p


def _resolve_save_dir(config_or_projects_dir: Path | str) -> Path:
    """Resolve directory to store project descriptors into."""
    p = Path(config_or_projects_dir)
    if p.name == "projects":
        return p
    if (p / "projects").is_dir():
        return p / "projects"
    return p / "projects"


def load_registered_projects(config_dir: Path | str) -> dict[str, str]:
    """Parse all <uuid>.json descriptors and build a mapping of folder_uri -> project_id.

    Excludes outside-of-project.json and descriptors without valid project resources.
    """
    projects_dir = _resolve_load_dir(config_dir)
    if not projects_dir.is_dir():
        return {}

    mapping: dict[str, str] = {}
    for json_file in projects_dir.glob("*.json"):
        # Exclude outside-of-project.json
        if json_file.name == "outside-of-project.json" or json_file.stem == "outside-of-project":
            continue

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        if not isinstance(data, dict):
            continue

        project_id = data.get("id")
        if not project_id or project_id == "outside-of-project":
            continue

        resources = data.get("projectResources")
        if not isinstance(resources, dict):
            continue

        res_list = resources.get("resources")
        if not isinstance(res_list, list):
            continue

        for res in res_list:
            if not isinstance(res, dict):
                continue

            folder_uri = None
            if "gitFolder" in res and isinstance(res["gitFolder"], dict):
                folder_uri = res["gitFolder"].get("folderUri")
            elif "folderUri" in res and isinstance(res["folderUri"], str):
                folder_uri = res.get("folderUri")

            if folder_uri and isinstance(folder_uri, str):
                norm = normalize_workspace_uri(folder_uri)
                mapping[norm] = project_id
                # Map unquoted variant if different (e.g. %20 vs space)
                unquoted_norm = normalize_workspace_uri(unquote(folder_uri))
                if unquoted_norm != norm:
                    mapping[unquoted_norm] = project_id

    return mapping


def register_new_project(
    config_dir: Path | str,
    workspace_uri: str,
    project_name: str | None = None,
) -> str:
    """Generate a new UUID, create a valid Antigravity project descriptor JSON, and return project_id."""
    projects_dir = _resolve_save_dir(config_dir)
    projects_dir.mkdir(parents=True, exist_ok=True)

    project_id = str(uuid.uuid4())
    canonical_uri = normalize_workspace_uri(workspace_uri)

    if not project_name:
        path_obj = _uri_to_path(canonical_uri)
        project_name = path_obj.name or "Project"

    # Detect git repository
    local_path = _uri_to_path(canonical_uri)
    is_git = (local_path / ".git").is_dir()

    if is_git:
        resource_entry = {
            "gitFolder": {
                "folderUri": canonical_uri,
            }
        }
    else:
        resource_entry = {
            "folderUri": canonical_uri,
        }

    descriptor = {
        "id": project_id,
        "name": project_name,
        "projectResources": {
            "resources": [
                resource_entry,
            ]
        },
        "permissionGrants": {
            "v2Migrated": True,
        },
        "settings": {},
        "isWorkspaceOnly": False,
    }

    target_file = projects_dir / f"{project_id}.json"
    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(descriptor, f, indent=2, ensure_ascii=False)

    return project_id


class ProjectRegistry:
    """High-level registry interface for querying, loading, and auto-registering projects."""

    def __init__(
        self,
        config_dir: Path | str | None = None,
        path_manager: PathManager | None = None,
    ) -> None:
        if path_manager is not None:
            self._projects_dir = path_manager.projects_dir
        elif config_dir is not None:
            self._projects_dir = _resolve_save_dir(config_dir)
        else:
            self._projects_dir = PathManager().projects_dir

        self._cache: dict[str, str] | None = None

    @property
    def projects_dir(self) -> Path:
        return self._projects_dir

    def load_projects(self, force_reload: bool = False) -> dict[str, str]:
        """Load and cache mapping of folder_uri -> project_id."""
        if self._cache is None or force_reload:
            self._cache = load_registered_projects(self._projects_dir)
        return self._cache

    def get_project_id(self, workspace_uri: str) -> str | None:
        """Find registered project_id for given workspace path or URI."""
        mapping = self.load_projects()
        norm = normalize_workspace_uri(workspace_uri)
        if norm in mapping:
            return mapping[norm]
        unquoted_norm = normalize_workspace_uri(unquote(workspace_uri))
        return mapping.get(unquoted_norm)

    def register(self, workspace_uri: str, project_name: str | None = None) -> str:
        """Register a new project descriptor and update internal cache."""
        project_id = register_new_project(
            config_dir=self._projects_dir,
            workspace_uri=workspace_uri,
            project_name=project_name,
        )
        self.load_projects(force_reload=True)
        return project_id

    def get_or_register(
        self, workspace_uri: str, project_name: str | None = None
    ) -> tuple[str, bool]:
        """Get existing project_id or register a new one. Returns (project_id, was_created)."""
        existing_id = self.get_project_id(workspace_uri)
        if existing_id:
            return existing_id, False

        new_id = self.register(workspace_uri, project_name=project_name)
        return new_id, True
