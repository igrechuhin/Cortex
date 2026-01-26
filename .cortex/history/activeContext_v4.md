# Active Context: Cortex

## Current Focus (2026-01-26)

See [roadmap.md](roadmap.md) for current status and milestones.

### Active Work

- 🟡 **Phase 53 Blockers** (2026-01-26) - Follow-up work remaining:
  - Memory bank index staleness breaks `manage_file(write)`
  - `fix_quality_issues` over-reporting remaining issues

- ✅ **Phase 9: Excellence 9.8+ COMPLETE** (2026-01-22) - Achieved 9.6/10 overall quality score
- ✅ **Phase 26: Unify Cache Directory Structure COMPLETE** (2026-01-22) - Unified cache directory implemented
- ✅ **Phase 53: Type Safety Cleanup** (2026-01-25) - See roadmap.md for detailed completion notes
- **Next milestone**: Phase 21 (Health-Check and Optimization Analysis System), Phase 27-29

### Recently Completed

- ✅ **Phase 53 Blocker: Commit pipeline ergonomics + scoping** - COMPLETE (2026-01-26) - Updated commit workflow docs to be `.cortex`-first (`.cursor` optional), added fail-fast quality preflight, and scoped markdown lint defaults to modified files (archives non-blocking by default)

- ✅ **Phase 53 Blocker: Cursor MCP `user-cortex` server errored (commit pipeline blocked)** - COMPLETE (2026-01-25) - MCP server healthy again; core tool calls succeed; roadmap + plan updated

- ✅ **Phase 26: Unify Cache Directory Structure** - COMPLETE (2026-01-22) - Refactored Cortex MCP tools to use unified cache directory:
  - Added `CACHE` to `CortexResourceType` enum and `get_cache_path()` helper
  - Updated `SummarizationEngine` to use `.cortex/.cache/summaries` by default
  - Created `cache_utils.py` module with utilities for cache management
  - Added comprehensive tests (23 new tests, all passing)
  - Updated README.md to document unified cache structure
  - All 54 tests passing, 0 linting errors, 0 type errors
  - Provides centralized cache management for all future caching needs

- ✅ **Phase 9.9: Final Integration & Validation** - COMPLETE (2026-01-22) - Completed Phase 9 Excellence 9.8+ initiative:
  - Comprehensive testing: 2,655 tests passing (100% pass rate), 90.15% coverage
  - Code quality validation: All checks passing (Black, Pyright, Ruff, file sizes, function lengths)
  - Quality report generated: Overall score 9.6/10 (exceeds 9.5/10 target)
  - Documentation updated: README.md, STATUS.md, memory bank files, completion summary created
  - All sub-phases complete: 9.1-9.9 all marked as COMPLETE
  - Key achievements: Zero file size violations, zero function length violations, zero type errors, zero linting violations
  - Security score: 9.8/10, Maintainability score: 9.8/10, Rules compliance: 9.8/10
  - Quality report available at `benchmark_results/phase-9-quality-report.md`

## Project Health

- **Test Coverage**: 90.15% (2662 tests passing, 2 skipped) ✅
- **Type Errors**: 0 (pyright src/ tests/) ✅
- **Type Warnings**: 0 (pyright src/ tests/) ✅
- **Linting Errors**: 0 (ruff check src/ tests/) ✅
- **Function Length Violations**: 0 ✅
- **File Size Violations**: 0 ✅
- **Performance Score**: 9.0/10
- **Security Score**: 9.8/10 ✅ (up from 9.5/10 via vulnerability fixes)
- **Overall Quality Score**: 9.6/10 ✅ (Phase 9 target achieved)

## Code Quality Standards

- Maximum file length: 400 lines
- Maximum function length: 30 logical lines
- Type hints: 100% coverage required
- Testing: AAA pattern, 90% minimum coverage (MANDATORY - NO EXCEPTIONS)
- Formatting: Black + Ruff (import sorting)

## Project Structure

```text
.cortex/                    # Primary Cortex data directory
├── memory-bank/           # Core memory bank files
├── plans/                 # Development plans
├── prompts/               # Cortex-specific prompts (NOT part of Synapse)
├── synapse/               # Shared rules (Git submodule) - language-agnostic only
├── history/               # Version history
├── .cache/                # Unified cache directory
│   ├── summaries/         # Summary cache files
│   └── [future subdirs]  # Future: relevance/, patterns/, refactoring/
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
