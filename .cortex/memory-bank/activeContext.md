# Active Context: Cortex

## Current Focus (2026-02-01)

See [roadmap.md](roadmap.md) for current status and milestones.

### Active Work

- ✅ **Commit (2026-02-01)**: Pre-commit pipeline; markdown lint 5 files fixed (activeContext, progress, roadmap, phase-34, docs/mcp-tool-timeouts). fix_errors, format, type_check, quality, tests 3304, coverage 90.35%. Plan archiving in Step 7.

- ✅ **Commit (2026-02-01)**: Pre-commit pipeline; markdown lint 2 files fixed (progress, phase-33). fix_errors, format, type_check, quality, tests 3303, coverage 90.36%. Plan archiving in Step 7.

- ✅ **Commit (2026-02-01)**: Pre-commit pipeline; markdown lint 3 files fixed (activeContext, progress, roadmap). fix_errors, format, type_check, quality, tests 3303, coverage 90.37%. Plan archiving in Step 7.

- ✅ **Commit (2026-02-01)**: Pre-commit pipeline; markdown lint MD037 fixes (progress, roadmap); fix_errors, format, type_check, quality, tests 3303, coverage 90.38%. Plan archiving in Step 7.

- ✅ **Phase 34: Ensure MCP tool timeouts** - COMPLETE (2026-02-01) - All tools had @mcp_tool_wrapper; synapse_repository uses asyncio.timeout; docs updated; verification test added. Quality gate passes.

- ✅ **Phase 33: Fix execute_pre_commit_checks JSON parsing error** - COMPLETE (2026-02-01) - Tool returns dict (ModelDict) so FastMCP serializes once; create_error_result_dict, unsupported_language_result_dict; _run_quality_checks uses dict directly. 3303 tests; quality gate passes.

- ✅ **Phase 32: Fix MCP tool connection closure errors** - COMPLETE (2026-02-01) - Pre-execution and before-retry health checks; connection state tracking; ConnectionError on connection failures; 3303 tests; coverage 90.38%; quality gate passes.

- ✅ **Commit (2026-02-01)**: Pre-commit pipeline; markdown lint 4 files fixed (activeContext, progress, roadmap, phase-31). fix_errors, format, type_check, quality, tests 3301, coverage 90.39%. Plan archiving in Step 7.

- ✅ **Phase 31: Fix optimize-context stale file errors** - COMPLETE (2026-02-01) - Existence check before read in load_context and load_progressive_context paths; read_file raises FileNotFoundError immediately (no retries). 3301 tests; coverage 90.39%; quality gate passes.

- ✅ **Phase 21: Health-Check and Optimization Analysis** - COMPLETE (2026-02-01) - Steps 6–9 done: CLI scripts/health_check.py; CI health-check step and artifact in .github/workflows/quality.yml; tests/tools/test_health_check_cli.py; docs/guides/health-check.md, docs/api/health-check.md, docs/api/tools.md (54 tools). Steps 2–4 implemented in module. All 3204 tests pass; coverage 90.83%.

- ✅ **Phase 20: Code Review Fixes** - COMPLETE (2026-02-01) - All steps done. Step 3.6 (initialization.py 188 lines) and 3.7 (structure_analyzer.py 264 lines) complete. All 10 file splits done; 3201 tests pass; quality gate passes. Plan: .cortex/plans/archive/Phase20/phase-20-code-review-fixes.md.

- ✅ **Phase 29: Track MCP tool usage** - COMPLETE (2026-02-01) - Usage tracking (UsageTracker, usage_models, usage_context); recording in mcp_stability; usage_analytics MCP tools; config usage_tracking.json. 3298 tests; coverage 90.27%; quality gate passes.

- ✅ **Phase 27: Script generation prevention** - COMPLETE (2026-02-01) - Steps 3–5, 7 done: script_promotion (validator, tool_converter, script_integrator, documentation_generator); discovery (tool_registry, use_case_mapper, search_interface, recommendation_engine); script_capture_tools extended with analyze_session_scripts, suggest_tool_improvements, promote_session_script; implement prompt script-generation-prevention note. 3283 tests; coverage 90.84%.

- ✅ **Phase 25: Fix CI failure (commit 302c5e2)** - COMPLETE (2026-02-01)
- ✅ **Phase 24: Fix roadmap text corruption** - COMPLETE (2026-02-01)
- ✅ **Phase 23: Fix CI failure (validation refactor)** - COMPLETE (2026-02-01)
- ✅ **Phase 21 Step 5 (analyze_health_check MCP tool)** - COMPLETE (2026-02-01)
- ✅ **Phase 20 Step 3.4 (rollback_manager split)** - COMPLETE (2026-02-01)
- ✅ **Phase 20 Step 3.5 (template_manager split)** - COMPLETE (2026-02-01)
- ✅ **Phase 20 Step 3.6 (initialization split)** - COMPLETE (2026-02-01)
- ✅ **Phase 20 Step 3.7 (structure_analyzer split)** - COMPLETE (2026-02-01)
- ✅ **Phase 20 Step 3.8 (optimization_strategies split)** - COMPLETE (2026-02-01)
- ✅ **Phase 20 Step 3.9 (phase8_structure split)** - COMPLETE (2026-02-01)
- ✅ **Phase 20 Step 3.10 (phase5_execution split)** - COMPLETE (2026-01-31)
- ✅ **Ensure proper logging (FastMCP context)** - COMPLETE (2026-01-31)
- ✅ **Conditional prompt registration** - COMPLETE (2026-01-31)

### Recently Completed

- Commit (2026-02-01): Pre-commit pipeline; markdown lint 5 files fixed. 3304 tests; coverage 90.35%. Plan archiving in Step 7.
- Commit (2026-02-01): Pre-commit pipeline; markdown lint 2 files fixed. 3303 tests; coverage 90.36%. Plan archiving in Step 7.
- Commit (2026-02-01): Pre-commit pipeline; markdown lint 3 files fixed. 3303 tests; coverage 90.37%. Plan archiving in Step 7.

## Project Health

- **Tests**: 3304 passing; coverage ≥ 90%.
- **Linting/Types**: Pyright 0 errors, 0 warnings.
- **Quality**: File size and function length gates passing; all 10 Phase 20 file splits ≤400 lines.
- **Pre-commit adapters**: Python, TypeScript, JavaScript, Rust, Go, Java, Kotlin, Swift full implementations.
- **Health-check**: CLI scripts/health_check.py; CI step in quality.yml; analyze_health_check MCP tool.
- **Script capture**: capture_session_script, list_session_scripts, analyze_session_scripts, suggest_tool_improvements, promote_session_script MCP tools; script_promotion and discovery modules; .cortex/script-capture/ storage.
- **Plans**: Plans directory in sync with roadmap.
- **Path resolution**: Use Cortex MCP tools (`get_structure_info()`, `manage_file()`, `rules()`) for memory bank and structure paths.

## Next Focus

- Pick next PENDING plan (Phase 35: Fix execute_pre_commit_checks MCP JSON error). Run commit pipeline when ready.
