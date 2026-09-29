# Antigravity Chat Migrator

<p align="center">
  <strong>Cross-platform CLI & utility to fix "Outside of Project" chats and synchronize Antigravity conversations across workspaces</strong>
</p>

<p align="center">
  <a href="README_RU.md">🇷🇺 Читать на русском</a> •
  <a href="README.md">🇬🇧 English</a>
</p>

<p align="center">
  <a href="https://github.com/Fuheshka/antigravity-chat-migrator/actions/workflows/ci.yml"><img src="https://github.com/Fuheshka/antigravity-chat-migrator/actions/workflows/ci.yml/badge.svg" alt="CI Status" /></a>
  <a href="https://github.com/Fuheshka/antigravity-chat-migrator/releases"><img src="https://img.shields.io/github/v/release/Fuheshka/antigravity-chat-migrator?color=blue&logo=github" alt="GitHub Release" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT" /></a>
  <a href="https://github.com/Fuheshka/antigravity-chat-migrator/releases"><img src="https://img.shields.io/badge/Platform-macOS%20%7C%20Windows-blue" alt="Platforms" /></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white" alt="Python 3.10+" /></a>
</p>

---

## Overview

**Antigravity Chat Migrator** (`agy-migrator`) is a high-reliability, zero-dependency utility engineered to repair, categorize, and synchronize conversation history in **Google Antigravity IDE**.

When workspaces are renamed, moved across drives, or transferred between IDE installations, Antigravity frequently detaches existing chats and dumps them into a generic **"Outside of Project"** collapsible group in the sidebar. Titles disappear, project associations break, and conversations become fragmented.

`agy-migrator` solves this at the root cause by deep-inspecting and reconciling SQLite trajectory databases, the `projects.json` workspace registry, Protobuf annotation files (`.pbtxt`), and the binary `language_server` cache (`agyhub_summaries_proto.pb`) across macOS and Windows.

```
   ___          __  _                         _  __       
  / _ | ___  __/ /_(_)__ ________ __  _____ _(_)/ /___ __ 
 / __ |/ _ \/ _  / // _ `/ __/ _ `/ |/ / // / // __/ // / 
/_/ |_/_//_/\_,_/_/ \_, /_/  \_,_/|___/\_, /_//_/  \_, /  
                   /___/              /___/       /___/   

  ⚡ Chat Repair, Workspace Sync & History Preserver
  📦 Version 0.1.0 • 🛡️ Cold-Disk Rule: safety-first synchronization
```

---

## Quick Start

### 1. Pre-built Binaries (No Python Required)

| Platform | Download | Instructions |
| :--- | :--- | :--- |
| **macOS** (Apple Silicon & Intel) | [**Antigravity-Chat-Migrator-macOS.dmg**](https://github.com/Fuheshka/antigravity-chat-migrator/releases) | Open DMG, drag `Antigravity Chat Migrator.app` into Applications, or copy `agy-migrator` to `/usr/local/bin`. |
| **Windows** (x64) | [**Antigravity-Chat-Migrator-Windows-x64.zip**](https://github.com/Fuheshka/antigravity-chat-migrator/releases) | Unzip to any folder, double-click `run_fix.bat` for one-click repair, or run `agy-migrator.exe` in Terminal. |

### 2. Python Package / CLI (Developer Install)

```bash
# Clone repository
git clone https://github.com/Fuheshka/antigravity-chat-migrator.git
cd antigravity-chat-migrator

# Install with pip
pip install .

# Or install in editable mode with development dependencies
pip install -e ".[dev]"

# Verify installation
agy-migrator --version
```

---

## The "Outside of Project" Problem

### Why Conversations Get Disconnected

Google Antigravity links conversations to workspaces through an internal multi-tiered architecture:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Antigravity IDE Storage                         │
├────────────────────────────────────────────────────────────────────────┤
│ 1. Workspace Registry:   ~/.gemini/config/projects.json                │
│    Maps URI (file:///path/to/project) -> project_id (UUID)             │
│                                                                        │
│ 2. Trajectory Database:  ~/.gemini/antigravity/conversations/<id>.db   │
│    Table: trajectory_metadata_blob                                     │
│    Protobuf Field 18: project_id (missing or "outside-of-project")     │
│    Protobuf Field 1:  WorkspaceInfo (file URI, git branch, repo metadata)│
│                                                                        │
│ 3. Global Summaries DB:  ~/.gemini/antigravity/conversation_summaries.db│
│    Table: summaries (conversation_id, title, project_id, raw_summary) │
│                                                                        │
│ 4. Language Server Cache:~/.gemini/antigravity/agyhub_summaries_proto.pb│
│    Binary Protobuf cache loaded in-memory by language_server daemon    │
│                                                                        │
│ 5. Chat Annotations:     ~/.gemini/antigravity/annotations/<id>.pbtxt  │
│    Protobuf TextFormat containing conversation title and timestamp    │
└────────────────────────────────────────────────────────────────────────┘
```

When a conversation falls into **"Outside of Project"**, one or more breaks have occurred:

1. **Unregistered Workspace:** The folder path was moved, reopened under an alias, or created before Antigravity assigned a `project_id` in `projects.json`.
2. **Metadata Mismatch:** Protobuf Field 18 inside `<conversation_id>.db` is empty or explicitly holds the `"outside-of-project"` sentinel string.
3. **Stale Summary Database:** The global `conversation_summaries.db` index points to an outdated or missing `project_id`.
4. **Protobuf Binary Cache Desync:** Even if the SQLite database is edited manually, the background `language_server` process maintains an in-memory binary cache (`agyhub_summaries_proto.pb`). When the IDE closes, it flushes stale in-memory state back to disk, overriding manual edits.
5. **Missing Annotations:** When `<conversation_id>.pbtxt` is missing, Antigravity fails to display chat titles, leaving entries blank or displaying placeholder labels.

### The Cold-Disk Invariant

> [!IMPORTANT]
> **Never modify Antigravity databases while the IDE or its language server is running.**
> Active Antigravity processes hold SQLite write locks (`PRAGMA locking_mode = EXCLUSIVE`) and cache conversation summaries in RAM. Modifying disk files while processes run risks database locking errors, corruption, or having the IDE overwrite your changes upon shutdown.
>
> `agy-migrator` enforces the **Cold-Disk Rule**: it detects active PIDs, warns you before executing changes, and provides a `--watch` mode that waits for clean IDE exit before synchronizing.

---

## CLI Commands

`agy-migrator` features a bilingual, high-contrast Rich terminal interface supporting both English and Russian (`--lang ru` / `--lang en`).

### 1. `audit` — Diagnostic Health Check (Read-Only)

Scans all conversations, checks workspace bindings, identifies unregistered directories, and reports missing annotations without altering any files on disk.

```bash
agy-migrator audit
```

```text
                       Chat & Workspace Audit Report                        
╭──────────────────────────────────────┬────────────┬──────────────────────╮
│ Metric                               │      Count │        Status        │
├──────────────────────────────────────┼────────────┼──────────────────────┤
│ Total conversations scanned          │        353 │       ✔ Ready        │
│ Bound to projects                    │        348 │         ✔ OK         │
│ Outside of project (unlinked)        │          5 │  ▲ Needs Attention   │
│ Missing annotations (.pbtxt)         │          3 │   ↻ Will be Fixed    │
│ Unregistered workspaces              │          2 │  ✖ Needs Attention   │
╰──────────────────────────────────────┴────────────┴──────────────────────╯

⚠️  Unregistered workspaces:
  • file:///Users/fuheshka/.gemini
  • file:///Users/fuheshka/Downloads/64Gram%20Desktop
```

### 2. `fix` — End-to-End Synchronization & Repair

Executes atomic repair across all tiers:
1. Creates a complete timestamped backup snapshot.
2. Auto-registers discovered workspace directories in `projects.json`.
3. Injects canonical `project_id` into SQLite `trajectory_metadata_blob` (Protobuf Field 18).
4. Generates missing `.pbtxt` annotation files with titles parsed directly from user requests in `transcript.jsonl`.
5. Patches `agyhub_summaries_proto.pb` binary cache.
6. Updates `conversation_summaries.db`.

```bash
# Standard interactive fix (prompts if IDE is open)
agy-migrator fix

# Dry-run mode (simulate changes without writing to disk)
agy-migrator fix --dry-run

# Watch mode: wait for Antigravity IDE to exit, then sync immediately
agy-migrator fix --watch

# Force mode: sync regardless of active processes (advanced)
agy-migrator fix --force
```

```text
ℹ️  Simulation mode (dry-run). No changes will be written to disk.

  • Conversations scanned: 353
  • Conversations updated: 5
  • Annotations generated: 3
  • Projects registered: 2

✔ Synchronization completed successfully.
```

### 3. `watch` — Background Process Watchdog

Monitors active Antigravity IDE and `language_server` processes. As soon as you exit the IDE, it automatically triggers a cold-disk synchronization.

```bash
agy-migrator watch
```

```text
⏳ Watchdog active: monitoring Antigravity IDE process lifecycle...
  [IDE Active: PID 12312, 12315] Waiting for graceful exit...
  [IDE Exited] Starting cold-disk synchronization...
✔ Synchronization completed successfully.
```

### 4. `rollback` — Snapshot Restoration & Rollback

Every `fix` operation creates a safety snapshot in `~/.gemini/antigravity/backups/migrator/`. If you ever need to revert, `rollback` restores previous databases, protobuf caches, and annotations instantly.

```bash
# List all available snapshots
agy-migrator rollback --list

# Restore the most recent snapshot
agy-migrator rollback

# Restore a specific snapshot by timestamp ID
agy-migrator rollback snapshot_20260930_001500
```

---

## Windows One-Click Launcher (`run_fix.bat`)

For Windows users, the release ZIP includes `run_fix.bat`, a portable double-clickable script:

1. Checks if `Antigravity.exe` is running and prompts to close it.
2. Runs `agy-migrator.exe audit` to display diagnostic metrics.
3. Asks for confirmation before making changes.
4. Executes `agy-migrator.exe fix` with automatic backup snapshot creation.
5. Displays a summary report and waits for keypress.

---

## Technical Architecture

```
src/antigravity_migrator/
├── __init__.py               # Package metadata and version info
├── cli.py                    # Typer & Rich CLI application commands
├── paths.py                  # Cross-platform path resolver (macOS & Windows)
├── proto_codec.py            # Zero-dependency pure-Python Protobuf bitwise codec
├── db_manager.py             # SQLite manager with busy_timeout and atomic UPSERT
├── project_registry.py       # projects.json workspace registration & URI normalizer
├── annotation_generator.py   # Transcript parser (.jsonl) and .pbtxt generator
├── backup_manager.py         # Timestamped snapshot backup & rollback manager
├── process_watcher.py        # Process lifecycle detection (psutil / native fallback)
├── service.py                # High-level orchestrator (audit & sync workflows)
├── ui_renderer.py            # High-contrast terminal banners, tables, and progress
└── i18n.py                   # Bilingual localization dictionary (RU & EN)
```

### Design Highlights
- **Zero-Dependency Protobuf Codec (`proto_codec.py`):** Encodes and decodes Protobuf wire types (0, 1, 2, 5) using pure Python bitwise operations (`<<`, `>>`, `&`, `|`). No `protoc` compiler or external `protobuf` library required.
- **Robust SQLite Handling (`db_manager.py`):** Configured with `PRAGMA busy_timeout = 5000` to prevent database locking errors during concurrent reads.
- **Transcript Extraction (`annotation_generator.py`):** Extracts human-readable conversation titles directly from the first user request in `transcript.jsonl`, stripping slash commands (`/goal`, `/using-superpowers`, `/vibe-coding`) and markdown formatting.
- **Cross-Platform Paths (`paths.py`):** Seamlessly handles Windows drive letters (`file:///C:/Users/...`) and macOS paths (`file:///Users/...`) with RFC 3986 URI normalization.

---

## Testing & Quality Assurance

The codebase includes an extensive suite of 114 unit and integration tests covering path normalization, protobuf encoding, database transactions, process detection, and Windows packaging:

```bash
# Run test suite
pytest -v

# Run with coverage report
pytest --cov=antigravity_migrator --cov-report=term-missing
```

```text
============================= 114 passed in 1.82s ==============================
```

CI workflows automatically validate all commits across **Ubuntu**, **macOS**, and **Windows** on Python 3.10, 3.11, and 3.12.

---

## Contributing

Contributions, bug reports, and suggestions are welcome!

1. Fork the repository.
2. Create a feature branch (`git checkout -b feat/my-improvement`).
3. Commit your changes using Conventional Commits (`git commit -m "feat: add support for custom project templates"`).
4. Push to your branch (`git push origin feat/my-improvement`).
5. Open a Pull Request.

---

## License

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.

Copyright (c) 2026 Daniil Kuviko (Fuheshka).
