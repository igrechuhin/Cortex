# Active Context: Cortex

## Current Focus (2026-01-13)

See [roadmap.md](roadmap.md) for current status and milestones.

### Active Work

- Code quality improvements: Fixed function length violations and type errors

### Recently Completed

- ✅ Code quality fixes (2026-01-13) - Fixed 3 function length violations by extracting helper functions
  - `_apply_optimization_strategy()` in `context_optimizer.py` - Extracted `_create_strategy_handlers()` helper
  - `configure()` in `configuration_operations.py` - Extracted `_get_component_handler()` helper
  - `_dispatch_validation()` in `validation_operations.py` - Extracted `_create_validation_handlers()` helper with type alias
- ✅ Type error fix (2026-01-13) - Fixed type error in `rules_indexer.py` by casting `status` to `str`
- ✅ [Phase 12: Convert Commit Workflow Prompts to MCP Tools](../plans/phase-12-commit-workflow-mcp-tools.md) - COMPLETE (2026-01-13)
- ✅ [Phase 9.3.4: Medium-Severity Optimizations](../plans/phase-9.3.4-medium-severity-optimizations.md) - COMPLETE (37/37 issues addressed, 2026-01-12)
- ✅ [Phase 11: Comprehensive MCP Tool Verification](../plans/phase-11-tool-verification.md) - All 29 tools verified
- ✅ [Phase 10.4: Test Coverage Improvement](../plans/phase-10.4-test-coverage-improvement.md) - 90.20% coverage achieved
- ✅ [Phase 3 Extension: Infrastructure Validation](../plans/phase-3-infrastructure-validation.md)

## Project Health

- **Test Coverage**: 90.32% (2318 tests passing, 2 skipped) ✅
- **Type Errors**: 0 ✅
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
