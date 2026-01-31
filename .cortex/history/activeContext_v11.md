# Active Context: Cortex

## Current Focus (2026-01-31)

See [roadmap.md](roadmap.md) for current status and milestones.

### Active Work

- **Ensure proper logging (FastMCP context)** - IN PROGRESS (2026-01-31)
  - Phase 1 and Phase 2 foundation done: logging guidelines (`docs/development/logging-guidelines.md`), `context_logging.py` (log_client, report_progress_safe), `manage_file` and `validate` refactored with optional ctx and client-visible logging. Unit tests: test_context_logging.py, TestValidateContextLogging in test_validation_operations.py. Remaining: Phase 2.3 (analyze, configure), Phases 3–5 (remaining tools, tests, docs). Plan: .cortex/plans/ensure-proper-logging-fastmcp.md.

- ✅ **Conditional prompt registration** - COMPLETE (2026-01-31)
- ✅ **Commit: type fix (reportPrivateUsage)** - COMPLETE (2026-01-31)
- ✅ **Session optimization (2026-01-31 review)** - COMPLETE (2026-01-31)
- ✅ **Sync plans with roadmap** - COMPLETE (2026-01-31)
- ✅ **Kotlin Pre-Commit Adapter** - COMPLETE (2026-01-31)
- ✅ **Swift Pre-Commit Adapter** - COMPLETE (2026-01-31)
- ✅ **Java Pre-Commit Adapter** - COMPLETE (2026-01-30)
- ✅ **Go Pre-Commit Adapter** - COMPLETE (2026-01-30)
- ✅ **Session hang: run pre-commit adapter work off event loop** - COMPLETE (2026-01-30)
- ✅ **Rust Pre-Commit Adapter** - COMPLETE (2026-01-30)
- ✅ **JavaScript Pre-Commit Adapter** - COMPLETE (2026-01-30)
- ✅ **Phases 64, 65, 66** - COMPLETE (2026-01-30)

### Recently Completed

- Ensure proper logging: validate tool refactored with Context logging (optional ctx, log_client for start/invalid/complete/error); TestValidateContextLogging added; 3143 tests passing, 90.45% coverage.
- Commit (2026-01-31): function length fix for `manage_file` (extracted `_manage_file_run_or_error`), markdown lint fixes (10 files), 3140 tests passing, 90.45% coverage.
- Ensure proper logging: Phase 1 (guidelines) and Phase 2 foundation (context_logging.py, manage_file with ctx logging).
- Conditional prompt registration: documentation for conditional prompt availability added.

## Project Health

- **Tests**: 3143+ passing; coverage ≥ 90%.
- **Linting/Types**: Pyright 0 errors, 0 warnings.
- **Pre-commit adapters**: Python, TypeScript, JavaScript, Rust, Go, Java, Kotlin, Swift full implementations.
- **Plans**: Plans directory in sync with roadmap.
- **Path resolution**: Use semantic names and Cortex MCP tools (`get_structure_info()`, `manage_file()`, `rules()`) for memory bank and structure paths; do not hardcode paths.

## Next Focus

- Continue **Ensure proper logging (FastMCP context)**: Phase 2.3 next tools (analyze, configure) or Phase 3 (remaining tools); or run commit pipeline when ready.
