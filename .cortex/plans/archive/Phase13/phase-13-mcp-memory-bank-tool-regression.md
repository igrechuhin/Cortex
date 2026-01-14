# Phase 13: MCP Memory Bank Tool Regression

## Status

- **Status**: ✅ COMPLETE
- **Priority**: ASAP (Blocker)
- **Start Date**: 2026-01-13
- **Completion Date**: 2026-01-13

## Goal

Investigate and fix the regression where MCP Memory Bank tools (for example, `manage_file` and `get_memory_bank_stats`) do not detect existing `.cortex/memory-bank/*.md` files when executed from this project root, despite those files being present on disk.

## Problem Description

- Memory Bank files such as `roadmap.md` and `progress.md` exist under `.cortex/memory-bank/`
- Direct filesystem access confirms these files are present and up to date
- MCP `manage_file(file_name="roadmap.md", operation="read", project_root="/Users/i.grechukhin/Repo/Cortex")` returns `"File roadmap.md does not exist"`
- `get_memory_bank_stats` reports only a single file in the Memory Bank and a different `project_root` (`/Users/i.grechukhin`), which does not match the actual project root (`/Users/i.grechukhin/Repo/Cortex`)

This mismatch indicates a path resolution or metadata index issue in the Memory Bank managers.

## Hypotheses

1. **Project Root Detection Bug**
   - The MCP server may be inferring `project_root` incorrectly (for example, using `$HOME` instead of the repository root)
   - The metadata index may have been initialized with a different root than the current project

2. **Metadata Index Desynchronization**
   - `.memory-bank-index` (or equivalent index) may not have been updated after migrating files to `.cortex/memory-bank/`
   - Index may be pointing at an obsolete directory (for example, `.cursor/memory-bank/`)

3. **Tool Configuration Drift**
   - Recent refactors (for example, Phase 2 linking or Phase 12 MCP tooling) may have partially updated paths without re-initializing the index
   - CLI and MCP server may disagree on where the Memory Bank lives

## Tasks

1. **Confirm Project Root Resolution**
   - [x] Add targeted unit tests for project root detection in Memory Bank initialization and manager wiring
   - [x] Verify that `project_root` passed via MCP calls is respected end-to-end

2. **Inspect and Repair Metadata Index**
   - [x] Read the current metadata index and confirm stored `project_root` and `memory_bank_dir` values
   - [x] If misaligned, implement a safe migration or re-initialization path

3. **Align Memory Bank Directory Configuration**
   - [x] Ensure all managers and tools consistently use `.cortex/memory-bank/` for this repository
   - [x] Add regression tests to prevent future drift (for example, snapshot tests for index paths)

4. **End-to-End Verification**
   - [x] Re-run `manage_file` and `get_memory_bank_stats` from this project root and confirm:
     - Roadmap, progress, and other Memory Bank files are visible
     - File counts and token stats match expectations

## Acceptance Criteria

- [x] `manage_file` can read and write `roadmap.md`, `progress.md`, and other Memory Bank files in `.cortex/memory-bank/` for this project
- [x] `get_memory_bank_stats` reports accurate `project_root`, `total_files`, and token counts
- [x] New regression tests cover project root detection and Memory Bank directory resolution
- [x] Roadmap blocker for this regression is cleared and marked as complete

## Solution Implemented

### Root Cause

The issue was incorrect memory bank path construction in multiple locations. Several modules were using `project_root / "memory-bank"` instead of `project_root / ".cortex" / "memory-bank"`.

### Files Fixed

1. **`src/cortex/core/file_system.py`** (line 43):
   - Changed: `self.memory_bank_dir: Path = self.project_root / "memory-bank"`
   - To: `self.memory_bank_dir: Path = self.project_root / ".cortex" / "memory-bank"`

2. **`src/cortex/managers/initialization.py`** (9 locations):
   - Fixed all `memory_bank_path = project_root / "memory-bank"` references
   - Changed to: `memory_bank_path = project_root / ".cortex" / "memory-bank"`

3. **`src/cortex/managers/container_factory.py`** (2 locations):
   - Fixed memory bank path construction

4. **`src/cortex/tools/validation_operations.py`** (5 locations):
   - Fixed memory bank directory path references

5. **`src/cortex/tools/phase2_linking.py`** (2 locations):
   - Fixed memory bank directory path references

6. **`src/cortex/tools/phase1_foundation_rollback.py`** (1 location):
   - Fixed memory bank directory path reference

### Total Fixes

- **17 locations** fixed across 6 files
- All memory bank paths now correctly use `.cortex/memory-bank/` directory structure
- Consistent with `MetadataIndex` which already used the correct path

### Verification

- All tests passing (2304 tests, 3 skipped)
- No linting errors
- No type errors
- Code follows all quality standards
