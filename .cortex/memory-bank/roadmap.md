# Roadmap: MCP Memory Bank

**Implementation sequence**: The implement command picks the **next** step as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Current Status (2026-02-01)

### Active Work

- ✅ **Conditional prompt registration** - COMPLETE (2026-01-31) - Implementation already present (src/cortex/tools/config_status.py, src/cortex/tools/prompts.py conditional registration). Documented conditional availability in README.md, docs/prompts/README.md, CLAUDE.md. All tests passing (3134); coverage 90.44%. Plan: .cortex/plans/conditional-prompt-registration.md.

- ✅ **Session optimization (2026-01-31 review)** - COMPLETE (2026-01-31) - Implemented recommendations from `.cortex/reviews/session-optimization-2026-01-31T15-00.md`: (1) Mandatory rules-load Pre-Step and BLOCK in commit prompt; checklist item "Rules loaded: Yes/No. If No, do not proceed to Step 0". (2) CRITICAL violation sentence for skipping rules load. (3) Error-fixer and type-checker agents: prerequisites to load rules before fixing, visibility/API guidance (test via public API; do not use reportPrivateUsage=false). (4) Common error "Fixing type/visibility without loaded rules" in commit prompt. (5) Project-wide rule for real-time references (Synapse rules): ALL time references MUST use real time; derive from mtime/tool/system date; NEVER use fallback or invented time. Updated analyze-session-optimization and session-optimization-analyzer accordingly.

- ✅ **Sync plans with roadmap** - COMPLETE (2026-01-31) - Archived completed plans to .cortex/plans/archive/Phase63/, .cortex/plans/archive/Phase67/enhance-tool-descriptions.plan.md, .cortex/plans/archive/Phase60/roadmap-sync-validation-error-ux.md. Added implement-next-roadmap-step fallback: when no pending step exists, run plan sync (archive completed plans) and update progress/activeContext.

- ✅ **Go Pre-Commit Adapter** - COMPLETE (2026-01-30) - Added GoAdapter in src/cortex/services/framework_adapters/go_adapter.py (go fmt, go vet, go build, go test). Registered in pre_commit_tools; go now uses GoAdapter instead of StubAdapter. StubAdapterLanguage no longer includes GO. Unit tests in tests/unit/test_go_adapter.py; test_get_adapter_returns_go_adapter_for_go in tests/unit/test_pre_commit_tools.py. Stub tests updated to use java. All 3020 tests passing.

- ✅ **Session hang: run pre-commit adapter work off event loop** - COMPLETE (2026-01-30) - Per `.cortex/reviews/session-hang-investigation-2026-01-30T15-00.md`: `execute_pre_commit_checks` now runs `_execute_all_checks` via `asyncio.to_thread()` so format, fix_errors, type_check, quality, and tests run off the event loop. Event loop stays responsive; MCP tool timeout still applies. Unit test `test_runs_adapter_checks_off_event_loop_via_to_thread` in tests/unit/test_pre_commit_tools.py. All 43 tests in that file passing.

- ✅ **Rust Pre-Commit Adapter** - COMPLETE (2026-01-30) - Added RustAdapter in src/cortex/services/framework_adapters/rust_adapter.py (cargo fmt, cargo clippy, cargo check, cargo test, cargo fix). Registered in pre_commit_tools; rust now uses RustAdapter instead of StubAdapter. StubAdapterLanguage no longer includes RUST. Unit tests in tests/unit/test_rust_adapter.py; test_get_adapter_returns_rust_adapter_for_rust in tests/unit/test_pre_commit_tools.py. Stub tests updated to use go/java. All 3000 tests passing.

- ✅ **JavaScript Pre-Commit Adapter** - COMPLETE (2026-01-30) - Added JavaScriptAdapter in src/cortex/services/framework_adapters/javascript_adapter.py (Prettier, ESLint for .js and .jsx, tsc --allowJs when configured, npm test). Registered in pre_commit_tools; javascript now uses JavaScriptAdapter instead of StubAdapter. Unit tests in tests/unit/test_javascript_adapter.py. test_get_adapter_returns_javascript_adapter_for_javascript in tests/unit/test_pre_commit_tools.py. All 2966 tests passing.

- ✅ **Commit: Coverage at 90% (helper tests)** - COMPLETE (2026-01-30) - Added tests/unit/test_configuration_helpers.py and tests/unit/test_analysis_helpers.py (parse_config_action, parse_analysis_target; invalid-value branch). Coverage 89.98% → 90%; 2951 tests passing. Markdown lint fixed 2 files.

- ✅ **Phase 64: Promote fixed string sets to enums** - COMPLETE (2026-01-30) - Milestones 1–4 done: ValidationCheckType, ConfigAction, AnalysisTarget, StubAdapterLanguage, FileOperation, RulesOperation, RefactoringAction, RefactoringSuggestionType enums added; file/rules tool boundaries use str; validate/configure/analyze parse to enum; tests updated. Milestone 4 (docs): docs/api/types.md Tool and Validation Enums section and str Enum pattern; Synapse python-coding-standards rule (str Enum for fixed sets, reserve Literal for one-off). Plan: .cortex/plans/archive/Phase64/phase-64-promote-fixed-strings-to-enums.md.

- ✅ **Commit: Coverage above 90%** - COMPLETE (2026-01-30) - Added tests/unit/test_refactoring_operation_helpers.py; coverage 89.98% → 90.01%; 2932 tests passing.

- ✅ **Phase 55: Improve Implementation Prompt Quality Gates** - COMPLETE (2026-01-29) - Added quality gates to .cortex/synapse/prompts/implement-next-roadmap-step.md: Step 3.5 Pydantic/TypedDict prohibition and pre-implementation checklist; Step 2 load_context error handling; Step 4 mandatory format and type-check steps, ReadLints before Step 4.5; Step 4.6 implicit-concatenation check; token budget 15k–20k for narrow steps. Python coding standards: TypedDict FORBIDDEN and validation step. Integration tests in tests/integration/test_implement_prompt_quality_gates.py. Plan: .cortex/plans/archive/Phase55/phase-55-improve-implementation-prompt-quality-gates.md.

- ✅ **Plan: Enhance Tool Descriptions with USE WHEN and EXAMPLES** - COMPLETE (2026-01-29) - Added USE WHEN, EXAMPLES, and RETURNS sections to all Cortex MCP tool docstrings across Phase 1–8 and utility tools (manage_file, get_memory_bank_stats, get_version_history, rollback_file_version, get_dependency_graph, cleanup_metadata_index; parse_file_links, validate_links, resolve_transclusions, get_link_graph; validate; load_context, load_progressive_context, summarize_content, get_relevance_scores; analyze, analyze_context_effectiveness, get_context_usage_statistics; suggest_refactoring, apply_refactoring, provide_feedback; sync_synapse, get_synapse_rules, get_synapse_prompts, update_synapse_rule, update_synapse_prompt; check_structure_health, get_structure_info; configure; execute_pre_commit_checks, fix_quality_issues; fix_markdown_lint, fix_roadmap_corruption; rules; check_mcp_connection_health). Plan file todos updated. All 461 tool tests passing.

- ✅ **Commit Procedure: Fixed Type Errors in Test Files** - COMPLETE (2026-01-28) - Fixed 8 type errors in test files: 2 unused call result errors (assigned to `_`) and 6 import errors (updated imports to use helper modules `file_operation_helpers` and `rules_operation_helpers`). All type checks passing (0 errors, 0 warnings). All tests passing (2868 passed, 2 skipped), coverage at 90.10%. All code quality gates passing.

- ✅ **Phase 57: Fix markdown_lint MCP Tool Timeout** - COMPLETE (2026-01-28) - **FIX-ASAP (resolved)** - The `fix_markdown_lint` MCP tool previously timed out after 300s when `check_all_files=True` because it processed archived plans. This is now fixed by excluding `.cortex/plans/archive/` in `_get_all_markdown_files()` to match CI behavior. See `../plans/archive/Phase57/phase-57-fix-markdown-lint-timeout.md` for implementation and verification details.

- ✅ **Phase 60: Improve `manage_file` Discoverability and Error UX** - COMPLETE (2026-01-28) - Implemented structured, friendly validation errors for `manage_file` (missing `file_name`/`operation` and invalid `operation` values), generalized the pattern to the `rules` MCP tool (missing `operation`), added focused tests in `tests/tools/test_file_operations.py` and `tests/tools/test_rules_operations.py`, and updated `docs/api/tools.md` plus Synapse prompts (commit/review) with explicit USE WHEN / EXAMPLES guidance for these tools.

- ✅ **Phase 62: Synapse Session Optimization – Harden Prompts and Rules** - COMPLETE (2026-01-29) - All steps 0–14 implemented. Cross-cutting improvements to Synapse prompts and rules: git write safety (Step 0), Step 11 submodule handling deterministic + Step 11.5 validation (Steps 1/11.5), roadmap_sync as true commit gate (Step 2), plan archiver Glob/Grep (Step 3), JSON boundary typing (Step 4), roadmap-sync blocking semantics (Step 5), sequential Step 12 + markdown lint Step 12.0 (Steps 6/6.5), manage_file anti-pattern (Step 7), MCP validation errors FIX-ASAP (Step 8), context budgets and memory bank selection (Step 9), post-commit recommendations (Step 10), session review filename conventions (Step 11), Pydantic v2 for JSON assertions in tests (Step 12), coverage handling for focused work (Step 13), session-analysis multi-signal and no_data handling (Step 14). Plan: `.cortex/plans/archive/Phase62/phase-62-synapse-session-optimization.md`.

## Future Enhancements

- ✅ **Commit Workflow Parallelization (Steps 9–11)** - COMPLETE (2026-01-29) - Plan: `.cortex/plans/archive/Phase56/phase-56-commit-workflow-parallelization.md`.

- ✅ **Multi-Language Pre-Commit Support** - COMPLETE (2026-01-29) - Added adapter registry (`_ADAPTER_REGISTRY`, SUPPORTED_LANGUAGES) and FrameworkAdapter typing in pre_commit_tools; quality check runs Python-specific file/function checks only when language is python; unsupported-language error lists supported languages from registry. Adding TypeScript/JavaScript/Rust/Go/Java adapters: implement FrameworkAdapter and register in `_ADAPTER_REGISTRY`.

- ✅ **Phase 63: Harden create-plan roadmap writes (full content and verification)** - COMPLETE (2026-01-29) - Added full-content-only rule for roadmap writes in `cortex/synapse/prompts/create-plan.md` Step 6 and `cortex/synapse/agents/memory-bank-updater.md`; added post-write verification in create-plan prompt Step 7 (confirm all existing entries unchanged, restore-and-repeat if truncation). Plan: .cortex/plans/archive/Phase63/phase-63-harden-create-plan-roadmap-writes.md.

- ✅ **Multi-Language Validation Support** - COMPLETE (2026-01-29) - Added StubAdapter for TypeScript, JavaScript, Rust, Go, Java and registered them in pre_commit_tools _ADAPTER_REGISTRY; SUPPORTED_LANGUAGES now includes 6 languages. Stub adapters return clear "not yet implemented" results until full implementations are added. Unit tests in tests/unit/test_stub_adapter.py and TestAdapterRegistry updates in tests/unit/test_pre_commit_tools.py. All 2906 tests passing.

- ✅ **TypeScript Pre-Commit Adapter** - COMPLETE (2026-01-29) - Added TypeScriptAdapter in src/cortex/services/framework_adapters/typescript_adapter.py (prettier, eslint, tsc, npm test). Registered in pre_commit_tools _ADAPTER_REGISTRY; typescript now uses TypeScriptAdapter instead of StubAdapter. Unit tests in tests/unit/test_typescript_adapter.py. TestAdapterRegistry updated (test_get_adapter_returns_typescript_adapter_for_typescript). All 2919 tests passing, coverage 90%.

- ✅ **Java Pre-Commit Adapter** - COMPLETE (2026-01-30) - Added JavaAdapter in src/cortex/services/framework_adapters/java_adapter.py (Maven/Gradle: spotless:apply/spotlessApply, compile/compileJava, validate/check, test). Registered in pre_commit_tools; java now uses JavaAdapter instead of StubAdapter. Unit tests in tests/unit/test_java_adapter.py; test_get_adapter_returns_java_adapter_for_java in tests/unit/test_pre_commit_tools.py. Stub tests updated to use other. All 3044 tests passing.

- ✅ **Kotlin Pre-Commit Adapter** - COMPLETE (2026-01-31) - KotlinAdapter in src/cortex/services/framework_adapters/kotlin_adapter.py (Maven/Gradle: Spotless/ktlint format, compile, validate/check, test). Registered in pre_commit_tools; kotlin uses KotlinAdapter. Unit tests in tests/unit/test_kotlin_adapter.py; test_get_adapter_returns_kotlin_adapter_for_kotlin in tests/unit/test_pre_commit_tools.py. Language detector supports Kotlin (Gradle or Maven config files, e.g. build.gradle, pom.xml). All adapter tests passing.

- ✅ **Swift Pre-Commit Adapter** - COMPLETE (2026-01-31) - SwiftAdapter in src/cortex/services/framework_adapters/swift_adapter.py (SwiftPM: swift format, swift build, swift test). Registered in pre_commit_tools; swift uses SwiftAdapter. Unit tests in tests/unit/test_swift_adapter.py; test_get_adapter_returns_swift_adapter_for_swift in tests/unit/test_pre_commit_tools.py. Language detector supports Swift (Package.swift). All adapter tests passing.

- **Pre-commit**: Add other language adapters as needed (src/cortex/tools/pre_commit_tools.py) – tracked; Python, TypeScript, JavaScript, Rust, Go, Java, Kotlin, and Swift have full implementations.

- ✅ **Phase 65: Commit Workflow — Cortex Tools Only** - COMPLETE (2026-01-30) - Removed all direct script invocations from the commit prompt; all pre-commit and Step 12 validation are invoked via Cortex MCP tools (`execute_pre_commit_checks` with format, format_ci_parity, type_check, quality, test_naming, tests; `fix_markdown_lint`). Added check types format_ci_parity and test_naming (run synapse scripts internally). Python adapter type_check now runs on src/ and tests/ to match CI. Integration test asserts the commit prompt file contains no `.venv/bin/python .cortex/synapse/scripts`. Plan: .cortex/plans/archive/Phase65/phase-65-commit-workflow-cortex-tools-only.md.

- ✅ **Phase 66: Plan Creation Workflow Compliance** - COMPLETE (2026-01-30) - Clarified path resolution in create-plan prompt (structure_info.paths.plans absolute, no hardcoding; Path resolution in ERROR HANDLING and IMPLEMENTATION GUIDELINES). Enforced roadmap update via manage_file only (Step 6 PROHIBITED/REQUIRED/VIOLATION; Step 7 restore via manage_file). Added memory-bank-updater "Roadmap update (plan creation)" note. Integration tests in tests/integration/test_plan_creation_workflow_compliance.py. Plan: .cortex/plans/archive/Phase66/phase-66-plan-creation-workflow-compliance.md.

## Pending plans (from .cortex/plans)

- ✅ **Ensure proper logging (FastMCP context)** - COMPLETE (2026-01-31) - Phase 3 tool migration done: phase4_optimization_handlers, context_analysis_handlers, phase8_structure, synapse_tools, pre_commit_tools, phase5_execution, refactoring_operations now use optional ctx and log_client; unit tests added (TestPhase4OptimizationContextLogging, TestContextAnalysisContextLogging, TestPhase8StructureContextLogging, TestSynapseToolsContextLogging, TestPreCommitToolsContextLogging, TestPhase5ExecutionContextLogging, TestRefactoringOperationsContextLogging). Some function-length/file-size quality violations remain; tracked for follow-up. Plan: .cortex/plans/ensure-proper-logging-fastmcp.md.

- **Phase 20: Code Review Fixes** - IN PROGRESS (2026-02-01) - Steps 1, 2, 4, 5 complete; Step 3.10 complete (phase5_execution split); Step 3.9 complete (phase8_structure split); Step 3.8 complete (optimization_strategies split). Remaining files >400 lines: rollback_manager, template_manager, initialization, structure_analyzer. All 3194 tests pass; quality gate passes. Plan: .cortex/plans/phase-20-code-review-fixes.md.

- **Phase 21: Health-Check and Optimization Analysis** - IN PROGRESS (2026-02-01) - Step 5 complete: MCP tool `analyze_health_check` in src/cortex/tools/health_check_operations.py (prompts, rules, tools, all; similarity_threshold, include_dependencies, validate_quality; optional prompt_dependencies/rule_dependencies). Public get_prompts_for_dependencies/get_rules_for_dependencies on analyzers. Tests: tests/tools/test_health_check_operations.py (10 tests). Quality gate passes. Remaining: Steps 2–4, 6–9. Plan: .cortex/plans/phase-21-health-check-optimization.md.

- ✅ **Phase 23: Fix CI failure (validation refactor)** - COMPLETE (2026-02-01) - Verified: all validation modules present; format, type_check, quality, tests pass (3194 passed, coverage 90.5%). CI failure from commit 612af0e resolved. Plan: .cortex/plans/archive/Phase23/phase-23-fix-ci-failure-validation-refactor.md.

- ✅ **Phase 24: Fix roadmap text corruption** - COMPLETE (2026-02-01) - Added Phase 24 phrase patterns to src/cortex/tools/roadmap_corruption.py (percent+to, number+ctual, ceeds, files unchanged, percent coverage, malformed date); fix_roadmap_content_if_needed and auto-fix on manage_file write for .cortex/memory-bank/roadmap.md; unit tests; quality gate passes. Plan: .cortex/plans/archive/Phase24/phase-24-fix-roadmap-text-corruption.md.

- ✅ **Phase 25: Fix CI failure (commit 302c5e2)** - COMPLETE (2026-02-01) - Verified: format, type_check, quality, tests pass (3201 passed, coverage 90.54%). CI failure from commit 302c5e2 resolved in current codebase. Plan: .cortex/plans/archive/Phase25/phase-25-fix-ci-failure-commit-302c5e2.md.

- **Phase 27: Script generation prevention** - PENDING - Plan: .cortex/plans/phase-27-script-generation-prevention.md.

- **Phase 29: Track MCP tool usage** - PENDING - Plan: .cortex/plans/phase-29-track-mcp-tool-usage.md.

- **Phase 30: Fix CI failure (commit 42a3362)** - PENDING - Plan: .cortex/plans/phase-30-fix-ci-failure-commit-42a3362.md.

- **Phase 31: Fix optimize-context stale file errors** - PENDING - Plan: .cortex/plans/phase-31-fix-optimize-context-stale-file-errors.md.

- **Phase 32: Fix MCP tool connection closure errors** - PENDING - Plan: .cortex/plans/phase-32-fix-mcp-tool-connection-closure-errors.md.

- **Phase 33: Fix execute_pre_commit_checks JSON parsing error** - PENDING - Plan: .cortex/plans/phase-33-fix-execute-pre-commit-checks-json-parsing-error.md.

- **Phase 34: Ensure MCP tool timeouts** - PENDING - Plan: .cortex/plans/phase-34-ensure-mcp-tool-timeouts.md.

- **Phase 35: Fix execute_pre_commit_checks MCP JSON error** - PENDING - Plan: .cortex/plans/phase-35-fix-execute-pre-commit-checks-mcp-json-error.md.

- **Phase 36: Enforce MCP tool failure protocol** - PENDING - Plan: .cortex/plans/phase-36-enforce-mcp-tool-failure-protocol.md.

- **Phase 42: Investigate execute_pre_commit_checks JSON error (commit 20260117)** - PENDING - Plan: .cortex/plans/phase-42-investigate-execute-pre-commit-checks-json-error-commit-20260117-122412.md.

- **Phase 43: Reconsider tools registration** - PENDING - Plan: .cortex/plans/phase-43-reconsider-tools-registration.md.

- **Phase 45: Add MCP annotations** - PENDING - Plan: .cortex/plans/phase-45-add-mcp-annotations.md.

- **Phase 46: Add progress reporting** - PENDING - Plan: .cortex/plans/phase-46-add-progress-reporting.md.

- **Phase 46: Extract setup to separate MCP server** - PENDING - Plan: .cortex/plans/phase-46-extract-setup-to-separate-mcp-server.md.

- **Phase 47: Add prompt icons and emoji in messages** - PENDING - Add emoji icons to prompts; use emoji in messages (e.g. ✅ success, ❌ error) where meaning is obvious. Plan: .cortex/plans/phase-47-add-prompt-icons.md.

- **Phase 48: Improve optimize-context feedback** - PENDING - Plan: .cortex/plans/phase-48-improve-optimize-context-feedback.md.

- **Phase 48: Optimize-context feedback analysis** - PENDING - Plan: .cortex/plans/phase-48-optimize-context-feedback-analysis.md.

- **Phase 49: Introduce Anthropic advanced tool use** - PENDING - Plan: .cortex/plans/phase-49-introduce-anthropic-advanced-tool-use.md.

- **Phase 53: Investigate Cursor MCP user-cortex server error** - PENDING - Plan: .cortex/plans/phase-53-investigate-cursor-mcp-user-cortex-server-error.md.

- **Phase 53: Investigate manage_file conflict/index stale** - PENDING - Plan: .cortex/plans/phase-53-investigate-manage-file-conflict-index-stale.md.

- **Phase 59: Investigate/fix markdown_lint MCP connection closed** - PENDING - Plan: .cortex/plans/phase-59-investigate-fix-markdown-lint-mcp-connection-closed.md.

- **Phase 9: Excellence 98** - PENDING - Plan: .cortex/plans/phase-9-excellence-98.md.

- **Refactor setup prompts (simplify to 3)** - PENDING - Simplify setup from 4 prompts to 3 (initialize, migrate, setup_synapse). Plan: .cortex/plans/refactor-setup-prompts.md.

- **Type cleanup inventory (Phase 53)** - PENDING - Inventory of dict[str, object], list[object], object, TypedDict, Any for type safety cleanup. Plan: .cortex/plans/type-cleanup-inventory.md.

- **Sequential thinking in Cortex MCP** - PENDING - Implement sequential thinking tool similar to MCP servers reference (thought history, revisions, branches). Plan: .cortex/plans/sequential-thinking-cortex-mcp.md.

- **Session optimization (2026-01-31 12-19): Public API, memory bank, SDK generics** - PENDING - Implement recommendations from session-optimization-2026-01-31T12-19 review: rule for public API not using private type names; prompt/agent to update memory bank after user-requested fixes; rule for SDK generic type parameters; one-time .cortex/memory-bank/progress.md alignment if needed. Plan: .cortex/plans/session-optimization-public-api-memory-bank-rules.md.
