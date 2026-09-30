"""Entry point for python -m antigravity_migrator.

Launches the native desktop GUI by default when invoked without arguments,
or executes subcommands and CLI flags if specified.
"""

from __future__ import annotations

import sys

from antigravity_migrator.cli import app

if __name__ == "__main__":
    # Filter out macOS LaunchServices Process Serial Number argument (-psn_...) if present
    if any(arg.startswith("-psn_") for arg in sys.argv):
        sys.argv = [arg for arg in sys.argv if not arg.startswith("-psn_")]
    app()
