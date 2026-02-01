# Roadmap: MCP Memory Bank

**Implementation sequence**: The implement command picks the **next** step as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Current Status (2026-02-01)

### Active Work

- ✅ **Conditional prompt registration** - COMPLETE (2026-01-31) - Implementation already present (src/cortex/tools/config_status.py, src/cortex/tools/prompts.py conditional registration). Documented conditional availability in README.md, docs/prompts/README.md, CLAUDE.md. All tests passing (3134); coverage 90.44%. Plan: .cortex/plans/conditional-prompt-registration.md.

- ✅ **Session optimization (2026-01-31 review)** - COMPLETE (2026-01-31) - Implemented recommendations from `.cortex/reviews/session-optimization-2026-01-31T15-00.md`: (1) Mandatory rules-load Pre-Step and BLOCK in commit prompt; checklist item "Rules loaded: Yes/No. If No, do not proceed to Step 0". (2) CRITICAL violation sentence for skipping rules load. (3) Error-fixer and type-checker agents: prerequisites to load rules before fixing, visibility/API guidance (test via public API; do not use reportPrivateUsage=false). (4) Common error "Fixing type/visibility without loaded rules" in commit prompt. (5) Project-wide rule for real-time references (Synapse rules): ALL time references MUST use real time; derive from mtime/tool/system date; NEVER use fallback or invented time. Updated analyze-session-optimization and session-optimization-analyzer accordingly.

- ✅ **Sync plans with roadmap** - COMPLETE (2026-01-31) - Archived completed plans to .cortex/plans/archive/Phase63/, .cortex/plans/archive/Phase67/enhance-tool-descriptions.plan.md, .cortex/plans/archive/Phase60/roadmap-sync-validation-error-ux.md. Added implement-next-roadmap-step fallback: when no pending step exists, run plan sync (archive completed plans) and update progress/activeContext.

- ✅ **Phase 20: Code Review Fixes** - COMPLETE (2026-02-01) - Steps 1, 2, 4, 5 complete; Step 3 complete (all 10 file splits: validation_operations, phase2_linking, pattern_analyzer, rollback_manager, template_manager, initialization, structure_analyzer, optimization_strategies, phase8_structure, phase5_execution). src/cortex/managers/initialization.py 188 lines; src/cortex/analysis/structure_analyzer.py 264 lines. All 3201 tests pass; quality gate passes. Plan: .cortex/plans/phase-20-code-review-fixes.md.

- ✅ **Phase 21: Health-Check and Optimization Analysis** - COMPLETE (2026-02-01) - Steps 6–9 done: CLI scripts/health_check.py (--type, --threshold, --output, --format json|markdown); CI health-check step and artifact in .github/workflows/quality.yml; tests/tools/test_health_check_cli.py; docs/guides/health-check.md, docs/api/health-check.md, docs/api/tools.md (54 tools, analyze_health_check). Steps 2–4 implemented in module (similarity_engine, dependency_mapper, quality_validator). All 3203 tests pass; coverage 90.84%. Plan: .cortex/plans/phase-21-health-check-optimization.md.

- ✅ **Phase 27: Script generation prevention** - COMPLETE (2026-02-01) - Steps 3–5, 7 done: script_promotion (validator, tool_converter, script_integrator, documentation_generator); discovery (tool_registry, use_case_mapper, search_interface, recommendation_engine); script_capture_tools extended with analyze_session_scripts, suggest_tool_improvements, promote_session_script; implement prompt script-generation-prevention note. All 3283 tests pass; coverage 90.84%; quality gate passes. Plan: .cortex/plans/phase-27-script-generation-prevention.md.

- ✅ **Go Pre-Commit Adapter** - COMPLETE (2026-01-30) - Added GoAdapter in src/cortex/services/framework_adapters/go_adapter.py (go fmt, go vet, go build, go test). Registered in pre_commit_tools; go now uses GoAdapter instead of StubAdapter. StubAdapterLanguage no longer includes GO. Unit tests in tests/unit/test_go_adapter.py; test_get_adapter_returns_go_adapter_for_go in tests/unit/test_pre_commit_tools.py. Stub tests updated to use java. All 3020 tests passing.

(rest of roadmap content unchanged - keeping Future Enhancements and Pending plans as in original)

- **Phase 29: Track MCP tool usage** - PENDING - Plan: .cortex/plans/phase-29-track-mcp-tool-usage.md.
