# Roadmap: MCP Memory Bank

## Current Status (2026-01-28)

### Active Work

- ✅ **Commit Procedure: Increased Test Coverage Above 90% Threshold** - COMPLETE (2026-01-27) - Added 3 tests for `check_approval_status` function in `src/cortex/tools/phase5_execution_helpers.py` to increase coverage from 89.99% to 90.05% (above threshold). All tests passing (2853 passed, 0 failed), coverage at 90.05%. All code quality gates passing.

- ✅ **Enhanced Python Adapter Ruff Fix with Verification** - COMPLETE (2026-01-26) - Enhanced `_run_ruff_fix()` method in `src/cortex/services/framework_adapters/python_adapter.py` to include verification step that matches CI workflow exactly. Split into two steps: auto-fix (`_execute_ruff_fix_command()`) and verification (`_execute_ruff_verify_command()`). Ensures no errors remain after auto-fix, preventing CI failures. All tests passing (2850 passed, 0 failed), coverage at 90.02%. All code quality gates passing.

- ✅ **Enhanced CI Workflow with Additional Pyright Error Patterns** - COMPLETE (2026-01-26) - Added two new pyright error patterns to `.github/workflows/quality.yml`: `reportOptionalSubscript` and `reportCallIssue`. Improves type safety enforcement in CI pipeline. All tests passing (2850 passed, 0 failed), coverage at 90.02%. All code quality gates passing.

- ✅ **Commit Procedure: Fixed Function Length Violation in Python Adapter** - COMPLETE (2026-01-26) - Fixed function length violation in `src/cortex/services/framework_adapters/python_adapter.py` by refactoring `_run_ruff_fix` function (34 lines → under 30) via extracting helper functions. All tests passing (2850 passed, 0 failed), coverage at 90%. All code quality gates passing.

- ✅ **Commit Procedure: Fixed Test Failures** - COMPLETE (2026-01-26) - Fixed 2 test failures: `test_update_file_metadata` (updated assertion to expect `version_info.model_dump(mode="json")`) and `test_setup_validation_managers_success` (fixed patch paths and added all 6 mocks). All tests passing (2850 passed, 0 failed), coverage at 90.01%. All code quality gates passing.

- ✅ **Commit Procedure: Fixed Type Error and Increased Test Coverage** - COMPLETE (2026-01-26) - Fixed type error in `src/cortex/services/framework_adapters/python_adapter.py` (implicit string concatenation) by adding explicit parentheses. Added 4 new tests for `_build_test_errors` method to increase coverage from 89.99% to 90.01% (above threshold). All tests passing (2834 passed, 0 failed), coverage at 90.01%. All code quality gates passing.

- ✅ **Commit Procedure: Fixed Function Length Violation and Increased Test Coverage** - COMPLETE (2026-01-26) - Fixed function length violation in `src/cortex/health_check/similarity_engine.py` by moving stop words to a private constant. Added 5 new tests to increase coverage from 89.95% to 90.0% (exactly at threshold). All tests passing (2830 passed, 0 failed), coverage at 90.0%. All code quality gates passing.

- ✅ **Commit Procedure: Fixed Function Length Violations and Added Health-Check Tests** - COMPLETE (2026-01-26) - Fixed 4 function length violations in health_check module by extracting helper functions. Added comprehensive tests (39 new tests) for health_check module to increase coverage from 88.08% to 90.04%. All tests passing (2805 passed, 2 skipped), coverage at 90.04%. All code quality gates passing.

- 🔄 **Phase 21: Health-Check and Optimization Analysis System - Step 1: Create Health-Check Analysis Module** - IN PROGRESS (2026-01-26) - Created `src/cortex/health_check/` module with all core components: PromptAnalyzer, RuleAnalyzer, ToolAnalyzer, SimilarityEngine, DependencyMapper, QualityValidator, ReportGenerator. All files within size limits (largest: 292 lines), all functions within length limits. Type checking: 0 errors, 0 warnings. Tests: 51 tests passing (7 similarity_engine, 5 quality_validator, 8 prompt_analyzer, 6 rule_analyzer, 8 tool_analyzer, 10 report_generator, 7 dependency_mapper). Code formatted with Black, all quality gates passing. Next: Step 2 (Implement Similarity Detection Engine enhancements).

- 🔄 **Phase 57: Fix markdown_lint MCP Tool Timeout** - IN PROGRESS (2026-01-27) - **FIX-ASAP** - The `fix_markdown_lint` MCP tool times out after 300s when `check_all_files=True` because it processes archived plans. Fixed by adding `.cortex/plans/archive/` to exclusion list in `_get_all_markdown_files()` to match CI behavior. See `../plans/phase-57-fix-markdown-lint-timeout.md` for details.

- 🔄 **Plan: Roadmap Sync & Validation Error UX Improvements** - PLANNED (2026-01-27) - See `../plans/roadmap-sync-validation-error-ux.md` for full design and testing strategy to clarify roadmap_sync semantics, improve path resolution for Phase plan references, and enrich MCP error messages for invalid references while preserving existing TODO tracking behavior.

- 🔄 **Plan: Enhance Tool Descriptions with USE WHEN and EXAMPLES** - PLANNED (2026-01-27) - See `../plans/enhance-tool-descriptions.plan.md` for comprehensive plan to improve all 53+ Cortex MCP tool descriptions by adding explicit "USE WHEN" triggers and "EXAMPLES" sections, following the pattern used in doc-mcp, taiga-ui-mcp, and react-mcp. This significantly improves tool discoverability for LLMs by making it clear when and how to use each tool.

- 🔄 **Phase 60: Improve `manage_file` Discoverability and Error UX** - PLANNED (2026-01-28) - See `../plans/phase-60-improve-manage-file-discoverability.plan.md` for investigation and implementation steps to make `manage_file` required parameters (`file_name`, `operation`) more discoverable, and to improve error responses when they are missing or invalid, especially in commit and memory-bank workflows.

- ✅ **Phase 61: Investigate `execute_pre_commit_checks` MCP Output Handling Failure** - COMPLETE (2026-01-28) - Updated `execute_pre_commit_checks` and `fix_quality_issues` MCP tools to always return compact, structured JSON results even when underlying checks produce very large textual logs. Added recursive log truncation for large `output` fields (preserving structured counts and statuses) so commit workflows can reliably parse `checks_performed`, `results`, and `stats` without relying on `agent-tools/*.txt` spill files. Added tests in `tests/unit/test_pre_commit_tools.py` to cover large-output scenarios and verify that quality results remain usable after truncation.

## Future Enhancements

- **Commit Workflow Parallelization (Steps 9–11)** - PLANNED - Implement a constrained parallelization block for commit Steps 9–11 (timestamp-validator, roadmap-sync-validator, submodule handling) based on the commit-parallelization analysis in the quality reviews. Keep Steps 0–8 and 12–14 strictly sequential, run Steps 9–11 in a structured TaskGroup, aggregate their results, and ensure Step 12 runs only after all three complete successfully. This work is tracked in the Phase 56 commit workflow parallelization plan.

- **Multi-Language Pre-Commit Support** - PLANNED - Add support for additional language adapters beyond Python - Currently only Python adapter is implemented - Location: src/cortex/tools/pre_commit_tools.py line 138 - TODO: Add other language adapters as needed (e.g., JavaScript/TypeScript, Rust, Go, Java, etc.) - This would enable pre-commit checks for multi-language projects

- **Multi-Language Validation Support** - PLANNED - Add support for additional language adapters in validation operations - Currently validation operations may need language-specific adapters - Location: src/cortex/tools/validation_operations.py line 351 - TODO: Add other language adapters as needed (e.g., JavaScript/TypeScript, Rust, Go, Java, etc.) - This would enable validation checks for multi-language projects
