# Active Context: Cortex

## Current Focus (2026-01-31)

See [roadmap.md](roadmap.md) for current status and milestones.

### Active Work

- ✅ **Commit: quality gate (function length + file size)** - COMPLETE (2026-01-31) - Fixed 7 function-length and 1 file-size violation: refactoring_operations (moved suggest_consolidation, suggest_splits, suggest_reorganization, process_refactoring_request, suggest_refactoring_error_json to refactoring_operation_helpers); file_operations (_log_manage_file_result); synapse_tools (_get_synapse_rules_error_json, _synapse_not_initialized_json); phase5_execution (_log_invalid_action_and_return, _log_apply_result,warn_suggestion_not_found_and_return). Tests: test_analysis_operations, test_consolidated patch targets updated to refactoring_operation_helpers. 3184 tests, 90.54% coverage.

- ✅ **Ensure proper logging (FastMCP context)** - COMPLETE (2026-01-31) - Phase 3 tool migration done; unit tests added. Plan: .cortex/plans/ensure-proper-logging-fastmcp.md.

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

- Commit (2026-01-31): quality gate (function length + file size); refactoring_operations split to helpers; file_operations, synapse_tools, phase5_execution helpers; test imports/patches updated. 3184 tests, 90.54% coverage.
- Commit (2026-01-31): quality gate fixes (pre_commit_tools, file_operations, refactoring_operations, synapse_tools, phase5_execution). 3184 tests, 90.55% coverage.

## Project Health

- **Tests**: 3184+ passing; coverage ≥ 90%.
- **Linting/Types**: Pyright 0 errors, 0 warnings.
- **Quality**: File size and function length gates passing.
- **Pre-commit adapters**: Python, TypeScript, JavaScript, Rust, Go, Java, Kotlin, Swift full implementations.
- **Plans**: Plans directory in sync with roadmap.
- **Path resolution**: Use Cortex MCP tools (`get_structure_info()`, `manage_file()`, `rules()`) for memory bank and structure paths.

## Next Focus

- Run commit pipeline when ready; or pick next roadmap step.
