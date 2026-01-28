# Active Context: Cortex

## Current Focus (2026-01-28)

See [roadmap.md](roadmap.md) for current status and milestones.

### Active Work

- ✅ **Phase 61: Investigate `execute_pre_commit_checks` MCP Output Handling Failure** - COMPLETE (2026-01-28)
  - `execute_pre_commit_checks` and `fix_quality_issues` now always return compact, structured JSON results, even when underlying checks produce very large textual logs.
  - Large `output` fields in check results are truncated via `_MAX_LOG_OUTPUT_LENGTH` and `_truncate_log_value()` with a clear "truncated" marker, while structured fields (`checks_performed`, `results`, `total_errors`, `total_warnings`, `files_modified`) remain intact.
  - This removes the commit pipeline’s dependency on `agent-tools/*.txt` spill files and ensures higher-level workflows in Cursor can reliably parse pre-commit results.
  - New tests in `tests/unit/test_pre_commit_tools.py` cover large-output scenarios and verify that quality results remain usable after truncation.

- ✅ **Phase: Roadmap Sync & Validation Error UX Improvements** - COMPLETE (2026-01-28)
  - Updated `src/cortex/validation/roadmap_sync.py` to resolve `plans/...` and `../plans/...` references using `get_cortex_path(project_root, CortexResourceType.PLANS)` instead of assuming project-root-relative paths, so roadmap references like ``../plans/phase-21-health-check-optimization.md`` correctly map to `.cortex/plans/...`.
  - Added structure-aware missing-file warnings that include the normalized reference, the resolved path (relative to project root when possible), and phase context, making invalid reference diagnostics more actionable.
  - Extended `SyncValidationResult` with a `total_todos_found` field and updated `src/cortex/tools/validation_roadmap_sync.py` to surface this in the `summary.total_todos_found` field for the `validate(check_type="roadmap_sync")` MCP tool.
  - Updated tests in `tests/tools/test_validation_operations.py` (and exercised existing `tests/unit/test_roadmap_sync.py` coverage) to assert the new behavior.

- ✅ **Commit Procedure: Fixed Line Length Violations and Test Failure** - COMPLETE (2026-01-27)
  - Fixed 4 line length violations in `test_version_manager.py`.
  - Fixed 1 test failure in `test_progressive_loader.py` by updating `test_loaded_content_creation()` to compare `FileContentMetadata` objects correctly.

- ✅ **Commit Procedure: Increased Test Coverage Above 90% Threshold** - COMPLETE (2026-01-27)
  - Added 3 tests for `check_approval_status` function in `phase5_execution_helpers.py` to increase coverage from 89.99% to 90.05%.

- ✅ **Enhanced Python Adapter Ruff Fix with Verification** - COMPLETE (2026-01-26)
- ✅ **Enhanced CI Workflow with Additional Pyright Error Patterns** - COMPLETE (2026-01-26)
- ✅ **Commit Procedure: Fixed Function Length Violation in Python Adapter** - COMPLETE (2026-01-26)
- ✅ **Commit Procedure: Fixed Test Failures** - COMPLETE (2026-01-26)
- ✅ **Commit Procedure: Fixed Type Error and Increased Test Coverage** - COMPLETE (2026-01-26)

### Recently Completed

- ✅ **Phase 57: Fix `fix_markdown_lint` MCP Tool Timeout** - COMPLETE (2026-01-28)
- ✅ **Commit Procedure: Fixed Function Length Violations and Added Health-Check Tests** - COMPLETE (2026-01-26)

## Project Health

- **Targeted Tests**: Roadmap sync and validation operation tests pass after enhancements.
- **Global Coverage Gate**: Full-suite coverage run from `pytest` currently reports ~21.7% due to large untested analysis/structure modules; roadmap_sync-specific code is covered (>90%) but repository-wide gate remains below 90%.
- **Linting/Types**: No Ruff or pyright issues reported for modified files.

## Next Focus

- Continue Phase 21 health-check enhancements (dependency mapping, quality preservation, MCP tool integration).
- Plan focused work to raise coverage in under-tested analysis/structure modules before re-enabling strict global coverage gates in day-to-day workflows.
