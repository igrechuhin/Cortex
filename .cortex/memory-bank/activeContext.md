# Active Context: Cortex

## Current Focus (2026-01-15)

See [roadmap.md](roadmap.md) for current status and milestones.

### Active Work

- Code quality maintenance: All pre-commit checks passing

### Recently Completed

- ✅ **Commit Procedure** (2026-01-15) - Fixed type errors and function length violations:
  - Fixed 5 type errors in `config_status.py` by adding missing type annotations (Path types)
  - Fixed 1 function length violation in `config_status.py` by extracting `_get_fail_safe_status()` helper
  - All linting errors fixed (0 remaining)
  - All files properly formatted (Black check passed)
  - Type checking: 0 actual type errors (excluding stub warnings)
  - All code quality checks passing (file size, function length)
  - All tests passing with 90.41% coverage (2,434 passed, 0 failed, 100% pass rate)
- ✅ [Phase 18: Markdown Lint Fix Tool](../plans/archive/Phase18/phase-18-markdown-lint-fix-tool.md) - COMPLETE (2026-01-14) - Created `scripts/fix_markdown_lint.py` tool that automatically scans modified markdown files (git-based), detects markdownlint errors, and fixes them automatically - Supports dry-run mode, JSON output, includes untracked files option, and comprehensive unit tests (16 tests, all passing)
- ✅ **Commit Procedure** (2026-01-15) - Fixed linting errors, type errors, and test failures:
  - Fixed 8 linting errors using ruff check --fix
  - Fixed 1 type error in `timestamp_validator.py` by casting issue to str
  - Fixed 2 test failures by updating tests to use date-only timestamps (YYYY-MM-DD) instead of datetime format
  - All tests passing with 90.50% coverage (2,399 passed, 2 skipped)
  - All code quality checks passing (file size, function length)

## Project Health

- **Test Coverage**: 90.41% (2,434 tests passing, 0 failed) ✅
- **Type Errors**: 0 (actual errors, excluding stub warnings) ✅
- **Type Warnings**: 22 (down from 48) ✅
- **Linting Errors**: 0 ✅
- **Performance Score**: 9.0/10

## Code Quality Standards

- Maximum file length: 400 lines
- Maximum function length: 30 logical lines
- Type hints: 100% coverage required
- Testing: AAA pattern, 90%+ coverage target
- Formatting: Black + Ruff (import sorting)

## Project Structure

```text
.cortex/                    # Primary Cortex data directory
├── memory-bank/           # Core memory bank files
├── plans/                 # Development plans
├── synapse/               # Shared rules (Git submodule)
├── history/               # Version history
└── index.json             # Metadata index

.cursor/                    # IDE compatibility (symlinks)
├── memory-bank -> ../.cortex/memory-bank
├── plans -> ../.cortex/plans
└── synapse -> ../.cortex/synapse
```

## Context for AI Assistants

### Key Files

- [roadmap.md](roadmap.md) - Current status and milestones
- [progress.md](progress.md) - Detailed progress log
- [productContext.md](productContext.md) - Product goals and architecture
- [systemPatterns.md](systemPatterns.md) - Technical patterns
- [techContext.md](techContext.md) - Technology stack

### Testing Approach

- Run targeted tests: `pytest tests/unit/test_<module>.py`
- Full test suite: `gtimeout -k 5 300 python -m pytest -q`
- Performance analysis: `scripts/analyze_performance.py`
