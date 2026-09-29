"""Process watcher module for detecting and waiting for Antigravity processes to terminate.

Provides cross-platform process discovery (macOS Darwin and Windows Win32)
to ensure safe "cold" database writes without SQLite file locks.
"""

from __future__ import annotations

import csv
import io
import os
import platform
import subprocess
import time
from typing import List, Optional

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore[assignment]


def is_antigravity_process_name(name: Optional[str]) -> bool:
    """Check if the given executable or process name corresponds to Antigravity or its language server.

    Matches:
    - 'Antigravity', 'Antigravity IDE'
    - 'Antigravity Helper', 'Antigravity Helper (Renderer)', etc.
    - 'language_server', 'language_server_macos', 'language_server_windows_x64.exe'
    - Windows executables (.exe)

    Excludes unrelated tools:
    - 'antigravity-tools', 'antigravity-chat-migrator', 'AntigravityQuota'
    """
    if not name or not isinstance(name, str):
        return False

    norm = name.strip().lower()
    if norm.endswith(".exe"):
        norm = norm[:-4]

    # Exact IDE binaries
    if norm in ("antigravity", "antigravity ide"):
        return True

    # Helper processes for the Electron / Antigravity app
    if norm.startswith("antigravity helper"):
        return True

    # Language server binary variants
    if norm == "language_server" or norm.startswith("language_server_"):
        return True

    return False


def _get_pids_via_psutil() -> List[int]:
    """Retrieve running Antigravity PIDs via psutil library."""
    pids: List[int] = []
    if psutil is None:
        return pids

    try:
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                p_name = proc.name() if callable(proc.name) else proc.info.get("name")
                if is_antigravity_process_name(p_name):
                    pids.append(proc.pid)
            except Exception:
                continue
    except Exception:
        pass

    return pids


def _get_pids_via_darwin_ps() -> List[int]:
    """Fallback PID detection on macOS / Unix using ps."""
    pids: List[int] = []
    try:
        proc = subprocess.run(
            ["ps", "-A", "-o", "pid=,comm="],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout:
            return pids

        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                continue
            pid_str, comm = parts
            try:
                pid = int(pid_str)
            except ValueError:
                continue

            binary_name = os.path.basename(comm)
            if is_antigravity_process_name(binary_name):
                pids.append(pid)
    except Exception:
        pass

    return pids


def _get_pids_via_windows_tasklist() -> List[int]:
    """Fallback PID detection on Windows using tasklist."""
    pids: List[int] = []
    try:
        proc = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout:
            return pids

        reader = csv.reader(io.StringIO(proc.stdout))
        for row in reader:
            if not row or len(row) < 2:
                continue
            image_name = row[0]
            pid_str = row[1]
            try:
                pid = int(pid_str)
            except ValueError:
                continue

            if is_antigravity_process_name(image_name):
                pids.append(pid)
    except Exception:
        pass

    return pids


def get_running_pids() -> List[int]:
    """Return PIDs of all currently running Antigravity IDE and language_server processes."""
    if psutil is not None:
        pids = _get_pids_via_psutil()
        if pids or psutil is not None:
            return sorted(list(set(pids)))

    # Fallback to OS commands if psutil is unavailable or returned empty due to environment
    sys_name = platform.system()
    if sys_name == "Windows":
        return sorted(list(set(_get_pids_via_windows_tasklist())))
    return sorted(list(set(_get_pids_via_darwin_ps())))


def is_antigravity_running() -> bool:
    """Return True if any Antigravity IDE or language_server process is currently running."""
    return len(get_running_pids()) > 0


def wait_for_shutdown(
    timeout_seconds: float = 60.0,
    poll_interval: float = 0.5,
    safety_pause: float = 1.0,
) -> bool:
    """Block execution until all Antigravity processes have exited.

    If processes were active, applies a safety pause (default 1.0s) after termination
    to allow OS file buffers and SQLite write-ahead logs to flush safely.

    Args:
        timeout_seconds: Maximum time in seconds to wait before giving up.
        poll_interval: Interval in seconds between process checks.
        safety_pause: Additional buffer pause in seconds after all processes exit.

    Returns:
        True if all processes exited within timeout or were already inactive;
        False if the timeout expired while processes remained running.
    """
    if not is_antigravity_running():
        return True

    start_time = time.monotonic()
    while (time.monotonic() - start_time) < timeout_seconds:
        time.sleep(poll_interval)
        if not is_antigravity_running():
            if safety_pause > 0:
                time.sleep(safety_pause)
            return True

    return False


class ProcessWatcher:
    """High-level watcher class for monitoring Antigravity application lifecycle."""

    def __init__(self, safety_pause: float = 1.0) -> None:
        self.safety_pause = safety_pause

    def is_running(self) -> bool:
        """Check if Antigravity or its language server is currently running."""
        return is_antigravity_running()

    def get_pids(self) -> List[int]:
        """Return a list of PIDs for running Antigravity processes."""
        return get_running_pids()

    def wait_for_shutdown(
        self,
        timeout_seconds: float = 60.0,
        poll_interval: float = 0.5,
    ) -> bool:
        """Wait for all Antigravity processes to terminate with the configured safety pause."""
        return wait_for_shutdown(
            timeout_seconds=timeout_seconds,
            poll_interval=poll_interval,
            safety_pause=self.safety_pause,
        )
