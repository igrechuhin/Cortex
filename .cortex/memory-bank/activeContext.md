# Active Context: Cortex

## Current Focus (2026-01-30)

See [roadmap.md](roadmap.md) for current status and milestones.

### Active Work

- **Commit in progress** (2026-01-30)
  - Type fixes: test_javascript_adapter (pyright reportPrivateUsage for _type_check_* helpers), test_pre_commit_tools (unused write_text result → _).
  - New test: test_run_tests_success_with_low_coverage_reports_error (JavaScript adapter coverage-below-threshold path).
  - Steps 0–4 passed: fix_errors, format, markdown lint (2 files fixed), type_check (0 errors), quality (0 violations), tests (2982 passed, 90.01% coverage).

- ✅ **JavaScript Pre-Commit Adapter** - COMPLETE (2026-01-30)
  - JavaScriptAdapter in src/cortex/services/framework_adapters/javascript_adapter.py (Prettier, ESLint .js/.jsx, tsc --allowJs when configured, npm test). Registered in pre_commit_tools; javascript uses JavaScriptAdapter. Unit tests in test_javascript_adapter.py; test_get_adapter_returns_javascript_adapter_for_javascript. All 2982 tests passing.

- ✅ **Phase 64: Promote fixed string sets to enums** - COMPLETE (2026-01-30)
  - Milestones 1–4 done: ValidationCheckType, ConfigAction, AnalysisTarget, StubAdapterLanguage, FileOperation, RulesOperation, RefactoringAction, RefactoringSuggestionType enums; tool boundaries use str and parse to enum; tests updated. Milestone 4: docs/api/types.md Tool and Validation Enums section and str Enum pattern; python-coding-standards.mdc guideline (str Enum for fixed sets, reserve Literal for one-off). Plan archived to .cortex/plans/archive/Phase64/. All 2951 tests passing.

- ✅ **Commit: Coverage at 90% (helper tests)** - COMPLETE (2026-01-30)
- ✅ **Phase 66: Plan Creation Workflow Compliance** - COMPLETE (2026-01-30)
- ✅ **Phase 65: Commit Workflow — Cortex Tools Only** - COMPLETE (2026-01-30)
- ✅ **Commit: Function length fix and plan archival** - COMPLETE (2026-01-30)
- ✅ **Commit: Coverage above 90%** - COMPLETE (2026-01-30)

### Recently Completed

- ✅ JavaScript Pre-Commit Adapter (JavaScriptAdapter, tests, registry).
- ✅ Phase 64 plan archived to .cortex/plans/archive/Phase64/.
- ✅ Phase 64 Milestone 4 (docs): types.md Tool and Validation Enums section; python-coding-standards str Enum guideline.
- ✅ Phase 64 Milestones 1–3 (enums for validation, config, analysis, stub adapter, file, rules, refactoring)
- ✅ Phase 66, Phase 65

## Project Health

- **Tests**: 2982 passing; coverage 90.01%.
- **Linting/Types**: Pyright 0 errors, 0 warnings.
- **Pre-commit adapters**: SUPPORTED_LANGUAGES = (python, typescript, javascript, rust, go, java); Python, TypeScript, and JavaScript have full implementations; Rust, Go, Java use StubAdapter.

## Next Focus

- No blockers. Next pending roadmap item or new enhancement from Future Enhancements (e.g. Rust/Go/Java adapters as needed).
