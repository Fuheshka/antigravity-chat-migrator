"""Annotation generator for Antigravity conversations.

Extracts meaningful conversation titles from transcript.jsonl and generates
Protobuf TextFormat (.pbtxt) annotation files.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import re


def _parse_timestamp(val: str | int | float | None) -> int | None:
    """Safely convert ISO timestamp string or numeric timestamp to Unix seconds."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return None
        # Try numeric string
        try:
            return int(float(val))
        except ValueError:
            pass
        # Try ISO 8601 string
        try:
            # Handle Zulu timezone suffix
            normalized = val.replace("Z", "+00:00")
            dt = datetime.fromisoformat(normalized)
            return int(dt.timestamp())
        except (ValueError, TypeError):
            return None
    return None


def _clean_title(raw_text: str, max_words: int = 10) -> str:
    """Extract a clean, concise title (up to max_words) from user query content."""
    if not raw_text:
        return "Untitled Conversation"

    # 1. Extract content from <USER_REQUEST> if present
    match = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>", raw_text, re.DOTALL | re.IGNORECASE)
    text = match.group(1) if match else raw_text

    # 2. Strip additional metadata and instructions
    text = re.sub(r"<ADDITIONAL_METADATA>.*", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)

    # 3. Process lines to find the first meaningful subject line
    candidate_line = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Skip slash command lines (e.g., /goal /vibe-coding ...)
        line_no_commands = re.sub(r"/[a-zA-Z0-9_\-]+", "", line).strip()
        if not line_no_commands:
            continue

        # Strip markdown headings and numbering (e.g. "### 1. Цель:", "## Goal:")
        cleaned = re.sub(r"^#+\s*(?:\d+[\.\)]\s*)?", "", line_no_commands).strip()
        cleaned = re.sub(r"^(?:Цель|Goal)[:\s\-]*", "", cleaned, flags=re.IGNORECASE).strip()

        if cleaned:
            candidate_line = cleaned
            break

    if not candidate_line:
        # Fallback to general text cleanup if no line was matched
        clean_text = re.sub(r"/[a-zA-Z0-9_\-]+", "", text)
        clean_text = re.sub(r"#+", "", clean_text).strip()
        candidate_line = clean_text

    # 4. Remove internal newlines/excess whitespace and backticks
    candidate_line = candidate_line.replace("`", "")
    words = candidate_line.split()
    if not words:
        return "Untitled Conversation"

    title_words = words[:max_words]
    title = " ".join(title_words).strip()
    return title if title else "Untitled Conversation"


def extract_title_from_transcript(transcript_path: Path) -> tuple[str, int | None]:
    """Extract conversation title and latest activity timestamp from transcript.jsonl.

    Args:
        transcript_path: Path to the transcript.jsonl file.

    Returns:
        A tuple of (title, timestamp_seconds).
    """
    path = Path(transcript_path)
    if not path.is_file():
        return "Untitled Conversation", None

    extracted_title: str | None = None
    last_timestamp: int | None = None

    try:
        with open(path, mode="r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    step = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue

                if not isinstance(step, dict):
                    continue

                # Parse timestamp if present
                if "created_at" in step:
                    ts = _parse_timestamp(step["created_at"])
                    if ts is not None:
                        if last_timestamp is None or ts > last_timestamp:
                            last_timestamp = ts

                # Look for first user request if title not yet found
                if extracted_title is None:
                    step_type = step.get("type", "")
                    step_source = step.get("source", "")
                    content = step.get("content")

                    is_user_step = (
                        step_type == "USER_INPUT"
                        or step_source == "USER_EXPLICIT"
                        or (isinstance(content, str) and "<USER_REQUEST>" in content)
                    )

                    if is_user_step and isinstance(content, str) and content.strip():
                        extracted_title = _clean_title(content)

    except OSError:
        pass

    # Fallback timestamp from file modification time if missing in transcript steps
    if last_timestamp is None:
        try:
            stat = path.stat()
            if stat.st_size > 0:
                last_timestamp = int(stat.st_mtime)
        except OSError:
            last_timestamp = None

    final_title = extracted_title if extracted_title else "Untitled Conversation"
    return final_title, last_timestamp


def generate_annotation_pbtxt(title: str, timestamp_seconds: int) -> str:
    """Generate Protobuf TextFormat (.pbtxt) content for conversation annotation.

    Args:
        title: Title of the conversation.
        timestamp_seconds: Unix timestamp in seconds for last_user_view_time.

    Returns:
        Formatted Protobuf TextFormat string.
    """
    # Sanitize title: single line, escape backslashes and double quotes
    sanitized_title = " ".join(title.replace("\r", " ").replace("\n", " ").split())
    escaped_title = sanitized_title.replace("\\", "\\\\").replace('"', '\\"')

    return (
        f'title: "{escaped_title}"\n'
        "last_user_view_time {\n"
        f"  seconds: {int(timestamp_seconds)}\n"
        "  nanos: 0\n"
        "}\n"
    )


def ensure_annotation_file(
    ann_path: Path,
    title: str,
    timestamp_seconds: int,
    overwrite: bool = False,
) -> bool:
    """Ensure an annotation .pbtxt file exists with the specified title and timestamp.

    Args:
        ann_path: Target path for the .pbtxt file.
        title: Conversation title.
        timestamp_seconds: Unix timestamp in seconds.
        overwrite: Whether to overwrite existing annotation file.

    Returns:
        True if the file was written, False if it already existed and overwrite was False.
    """
    path = Path(ann_path)
    if path.is_file() and not overwrite:
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    content = generate_annotation_pbtxt(title, timestamp_seconds)
    path.write_text(content, encoding="utf-8")
    return True


class AnnotationGenerator:
    """Static helper class for generating Antigravity conversation annotations."""

    extract_title_from_transcript = staticmethod(extract_title_from_transcript)
    generate_annotation_pbtxt = staticmethod(generate_annotation_pbtxt)
    ensure_annotation_file = staticmethod(ensure_annotation_file)
