# Tech Context: Cortex

**Schema Extension Note**: This file has schema validation with required sections (`## Technology Stack`, `## Dependencies`, `## Development Setup`). When adding new content, maintain proper heading hierarchy and avoid skipping heading levels. See `memory-bank-workflow.mdc` for detailed extension guidance.

## Technology Stack

## Languages and Runtime

- **Python 3.13** – Modern Python with built-in types (e.g., `list[str]`, `dict[str, int]`).

## Core Libraries

- **FastMCP** – MCP server framework.
- **aiofiles** – Async file I/O operations.
- **tiktoken** – Token counting for language models.
- **watchdog** – File system event monitoring.

## Tooling

- **pytest** – Testing framework.
- **pytest-timeout** – Test timeout management.
- **pytest-cov** / **coverage** – Test coverage tracking.
- **Black** – Code formatting.
- **Ruff** – Linting and import sorting.
- **Pyright** – Type checking.

## Development Setup

## Prerequisites

- Python 3.13+
- UV package manager (recommended) or pip
- Git

## Installation

```bash
# With UV (recommended)
uv sync --dev

# Or with pip
pip install -e ".dev]"
```

## Virtual Environment

- Default location: `.venv/`
- Python interpreter: `.venv/bin/python`
- All tools use `.venv/bin/` binaries

## Technical Constraints

- **File Size Limits**: Maximum400per file (production code)
- **Function Size Limits**: Maximum 30 logical lines per function
- **Type Coverage**: 100% type hints required (no `Any` type)
- **Test Coverage**: 90%+ target for all modules
- **Async Only**: All I/O operations must be async
- **No Global State**: All dependencies injected via constructors
- **One Public Type Per File**: Single public class/type per module

## Coding Standards

**Pydantic 2 Standards**: Pydantic 2 standards are owned by Synapse and defined in `python-pydantic-standards.mdc` (Synapse rules directory). For Pydantic 2 guidance, use `rules(operation="get_relevant", task_description="Pydantic 2 standards")` or `get_synapse_rules(task_description="Pydantic 2")` to load the canonical Synapse rule. Do not duplicate Pydantic guidance in this file.

## Dependencies

## Core Dependencies

- `fastmcp` – MCP server framework
- `aiofiles` – Async file operations
- `tiktoken` – Token counting
- `watchdog` – File watching

## Development Dependencies

- `pytest` – Testing framework
- `pytest-timeout` – Test timeouts
- `pytest-cov` – Coverage tracking
- `black` – Code formatting
- `ruff` – Linting and import sorting
- `pyright` – Type checking

## Tool Usage Patterns

**NOTE**: These are examples for THIS project (Python). For language-agnostic procedures, prefer Cortex MCP tool `execute_pre_commit_checks()` or use scripts from the Synapse scripts directory (path from project structure or `get_structure_info()`).

## Code Formatting (This Project – Python)

```bash
./.venv/bin/black .
./.venv/bin/ruff check --fix .
```

## Type Checking (This Project – Python)

```bash
./.venv/bin/pyright src/ tests/
```

## Testing (This Project – Python)

```bash
# Run all tests
./.venv/bin/pytest --session-timeout=300

# Run specific test file
./.venv/bin/pytest tests/unit/test_file.py

# With coverage
./.venv/bin/pytest --cov=src --cov-report=html
```

## Language-Agnostic Pattern (For Procedures)

**CRITICAL**: When writing procedures or prompts, use semantic names and Cortex tools:

- **Prefer Cortex MCP tools**: Use `execute_pre_commit_checks(checks=[...])` for format, type_check, quality, tests instead of invoking scripts directly.
- **If using scripts**: Refer to the "Synapse scripts directory" (path from project structure or `get_structure_info()` if available) and the language-specific script (e.g. check_linting, check_types). Do not hardcode `.cortex/synapse/scripts/` paths.
- **Wrong**: Hardcoding language-specific commands (e.g. `ruff check src/ tests/`) in prompts.

Scripts auto-detect:

- Project language (Python, TypeScript, Rust, etc.)
- Appropriate tools (ruff/black for Python, eslint/prettier for JS/TS, etc.)
- Source/test directories
- Build system (.venv, uv, system tools)

## MCP Server Execution

```bash
# Development mode
python -m cortex.main

# Or via UV
uv run cortex
```

## Project Structure

```text
Cortex/
├── src/cortex/          # Main source code
│   ├── core/            # Core functionality (Phase 1)
│   ├── linking/         # DRY linking (Phase 2)
│   ├── validation/      # Validation (Phase 3
│   ├── optimization/    # Token optimization (Phase 4
│   ├── analysis/        # Pattern analysis (Phase5)
│   ├── refactoring/     # Refactoring tools (Phase 5)
│   ├── rules/           # Shared rules (Phase6)
│   ├── structure/       # Project structure (Phase 8)
│   ├── tools/           # MCP tool implementations
│   └── managers/        # Manager initialization
├── tests/               # Test suite
│   ├── unit/            # Unit tests
│   └── integration/     # Integration tests
├── .cursor/             # Cursor IDE integration
│   ├── memory-bank/     # Memory bank files
│   ├── rules/           # Project rules
│   └── plans/           # Development plans
└── docs/                # Documentation
```

## Path Resolution and Cortex Tools (MANDATORY)

**Use semantic names and Cortex MCP tools** for all structure and memory bank access. Do not hardcode paths.

- **Memory bank**: Use `manage_file(file_name="...", operation="read"|"write")` to read/write memory bank files (e.g. roadmap.md, progress.md, activeContext.md). Do not hardcode the memory bank directory path.
- **Structure paths**: Use `get_structure_info()` → `structure_info.paths.plans`, `structure_info.paths.memory_bank`, `structure_info.paths.rules`, `structure_info.paths.reviews` for plans, memory bank, rules, and reviews directories.
- **Rules**: Prefer `rules(operation="get_relevant", task_description="...")` to load rules; if reading rule files, use the rules directory path from `get_structure_info()`.
- **Procedures and prompts**: Refer to "plans directory", "memory bank", "Synapse agents directory", etc., and resolve actual paths via Cortex tools.

## Memory Bank Location

- **Access**: Use Cortex MCP tool `manage_file(file_name="...", operation="read"|"write")`; resolve path via `get_structure_info()` → `structure_info.paths.memory_bank` if needed.
- **Core Files**: projectBrief.md, productContext.md, activeContext.md, systemPatterns.md, techContext.md, progress.md, roadmap.md
- **Metadata**: Managed by Cortex (index, version history)
- **Structure & responsibilities**: See the canonical "Memory Bank Structure (Canonical Spec)" section in the Memory Bank workflow rule for each file's single dedicated goal.

## Code Quality Standards

- **Formatting**: Black (88 columns) + Ruff (import sorting)
- **Type Hints**: 100% coverage, Python 3.13 built-ins only
- **Testing**: AAA pattern, 90% coverage
- **File Size**: ≤400s (excluding license/imports)
- **Function Size**: ≤30 logical lines
- **No Global State**: Dependency injection only
- **Async I/O**: All file operations must be async

## Performance Targets

- Context loading: <100ms for typical projects
- Token optimization: Efficient within budget constraints
- File operations: Async with locking for safety
- Test execution: <10s per test case, <300s total session

## Memory Bank History vs Git

## Current Behavior (2026-03-03)

- Snapshots are created by the Memory Bank write flow (`manage_file(operation="write")` via `crud_flow._execute_write_flow` and `create_version_snapshot`) and stored under the Cortex HISTORY path (typically `.cortex/history/`) as `<file>_v<version>.md`.
- Version metadata stored in `.cortex/index.json` records `snapshot_path`, `size_bytes`, `token_count`, `change_type`, optional `changed_sections`, and an optional `change_description` for each snapshot.
- Rollback helpers (`foundation_rollback_helpers` and rollback tools) resolve snapshot paths from version metadata and read content from `.cortex/history` via `VersionManager.get_snapshot_content` when executing `manage_file(..., operation="rollback")`. A successful rollback writes the rolled-back content back to the memory bank, increments the version, and creates a new snapshot tagged as a `rollback` change.
- Migration flows (`MigrationManager`) create initial snapshots for each existing memory-bank file when bootstrapping `.cortex/index.json`, verify that `.cortex/history` and snapshots exist, and remove `.cortex/history` entirely when rolling back a failed migration.
- Session compaction (`compact_session`) writes compacted `activeContext.md` and `progress.md` using the same internal write flow as `manage_file`, so it also creates snapshots and version-history entries for those writes.
- Memory-bank statistics (`get_memory_bank_stats` / `query_memory_bank(query_type="stats")`) call `VersionManager.get_disk_usage()` internally to compute total bytes stored in history; concise stats currently expose total file/tokens usage but not the raw history byte count.

## Comparison with Git

- Git provides per-commit history, branch-aware diffs, and recovery of committed memory-bank files over long time horizons.
- `.cortex/history` provides per-write snapshots for Memory Bank files, including writes that have not yet been committed to git (for example, auto-compaction or local edits done via MCP tools).
- History snapshots are per-file and not tied to git branches, so they can capture intermediate states even when the git branch changes or before a commit is made.
- Git remains the source of truth for long-term history; `.cortex/history` acts as a local, IDE-centric safety layer around migration, compaction, and rollback flows.

## Usage and Cost

- Version history is bounded by `VersionManager.keep_versions` (default 10 snapshots per file), so per-file history growth is limited by configuration rather than unbounded.
- The Memory Bank currently tracks 10 files and ~15k tokens, and concise stats report healthy token usage (~15% of the configured budget). History disk usage is tracked internally via `VersionManager.get_disk_usage()` and surfaced into detailed stats, but only summarized totals (file count, tokens, usage percentage) are available via concise stats/resources.
- Within current defaults, worst-case history size is roughly "10 snapshots × number of Memory Bank files", with each snapshot storing a full copy of the file at that point in time.

## Options and Recommendation

- **Option 1 – Keep and clarify**: Keep `.cortex/history` as a bounded safety net for Memory Bank writes and migration/rollback flows, and tighten documentation so users understand when to reach for rollback vs when to rely on git.
- **Option 2 – Simplify and limit**: Keep `.cortex/history` but treat it explicitly as an ephemeral, IDE-local safety history (short retention window and/or smaller `keep_versions`), and consider surfacing history size and per-file snapshot counts in user-facing stats so excessive growth is easy to spot.
- **Option 3 – Phase out**: Remove automatic snapshot writes from standard flows and rely on git for history, keeping only minimal safety helpers for migrations or explicit backups.
- **Recommended next step (2026-03-03)**: Treat `.cortex/history` as an internal, bounded safety layer on top of git (between Options 1 and 2). In a follow-up plan, refine retention (e.g., configurable `keep_versions` and clearer docs) and decide whether additional user-facing stats are needed before considering a full phase-out.
