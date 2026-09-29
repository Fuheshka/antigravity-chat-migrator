"""Cross-platform path resolution for Antigravity & Gemini configuration."""

from __future__ import annotations

import os
import platform
from pathlib import Path


class PathManager:
    """Manages cross-platform paths for Antigravity databases, caches, and project configs."""

    def __init__(
        self,
        data_dir: Path | str | None = None,
        config_dir: Path | str | None = None,
        system: str | None = None,
    ) -> None:
        self.system = system or platform.system()

        # Resolve Antigravity data directory (~/.gemini/antigravity)
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        elif os.environ.get("GEMINI_DATA_DIR"):
            self._data_dir = Path(os.environ["GEMINI_DATA_DIR"])
        else:
            self._data_dir = Path.home() / ".gemini" / "antigravity"

        # Resolve Gemini config directory (~/.gemini/config)
        if config_dir is not None:
            self._config_dir = Path(config_dir)
        elif os.environ.get("GEMINI_CONFIG_DIR"):
            self._config_dir = Path(os.environ["GEMINI_CONFIG_DIR"])
        else:
            self._config_dir = Path.home() / ".gemini" / "config"

    @property
    def data_dir(self) -> Path:
        """Root data directory for Antigravity conversations and caches."""
        return self._data_dir

    @property
    def config_dir(self) -> Path:
        """Root config directory for Gemini settings and projects."""
        return self._config_dir

    @property
    def projects_dir(self) -> Path:
        """Directory containing project UUID JSON descriptors."""
        return self._config_dir / "projects"

    @property
    def conversations_dir(self) -> Path:
        """Directory containing individual conversation SQLite databases (<uuid>.db)."""
        return self._data_dir / "conversations"

    @property
    def annotations_dir(self) -> Path:
        """Directory containing protobuf text annotations (<uuid>.pbtxt)."""
        return self._data_dir / "annotations"

    @property
    def brain_dir(self) -> Path:
        """Directory containing conversation transcripts, plans, and artifacts (<uuid>/)."""
        return self._data_dir / "brain"

    @property
    def summaries_pb(self) -> Path:
        """Path to binary protobuf summary cache file (agyhub_summaries_proto.pb)."""
        return self._data_dir / "agyhub_summaries_proto.pb"

    @property
    def summaries_db(self) -> Path:
        """Path to main SQLite registry database (conversation_summaries.db)."""
        return self._data_dir / "conversation_summaries.db"

    @property
    def backups_dir(self) -> Path:
        """Directory used for safety snapshots before modifications."""
        return self._data_dir / ".backups"

    def normalize_uri(self, path_or_uri: str | Path) -> str:
        """Convert a local file path into a canonical Antigravity file URI (file:///...)."""
        raw = str(path_or_uri).strip()
        if raw.startswith("file://"):
            return raw

        # Normalize backslashes to forward slashes
        clean_path = raw.replace("\\", "/")

        # Windows drive letter pattern, e.g. C:/Users/... -> file:///C:/Users/...
        if len(clean_path) >= 2 and clean_path[1] == ":" and clean_path[0].isalpha():
            return f"file:///{clean_path}"

        # Standard Unix path, e.g. /Users/... -> file:///Users/...
        if clean_path.startswith("/"):
            return f"file://{clean_path}"

        # Relative or unrooted path fallback
        return f"file:///{clean_path}"

    def uri_to_path(self, uri: str) -> Path:
        """Convert an Antigravity file URI back to a local filesystem Path."""
        if not uri.startswith("file://"):
            return Path(uri)

        path_part = uri[7:]  # Remove 'file://'
        # Windows file:///C:/Users/... -> C:/Users/...
        if self.system == "Windows" and path_part.startswith("/") and len(path_part) >= 3 and path_part[2] == ":":
            path_part = path_part[1:]
        return Path(path_part)

    def ensure_dirs(self) -> None:
        """Ensure all required directories exist on disk."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.conversations_dir.mkdir(parents=True, exist_ok=True)
        self.annotations_dir.mkdir(parents=True, exist_ok=True)
        self.brain_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)
