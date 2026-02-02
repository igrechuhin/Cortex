# Active Context: Cortex

## Current Focus (2026-02-02)

See [roadmap.md](roadmap.md) for current status and milestones.

### Active Work

- **Commit (2026-02-02)**: Pre-commit pipeline; markdown lint 5 files fixed (memory bank, phase-43 plans). 3311 tests, coverage 90.42%. 0 plans archived.

- **Phase 43: Reconsider tools registration (Step 2 complete)** (2026-02-02) - Design complete: .cortex/plans/phase-43-resource-api-design.md (URI scheme `cortex://`, `mcp.resource()` syntax verified, `mcp_resource_wrapper` and usage tracking with `handler_kind`, hybrid split strategy). Next: Step 3 Implement Resources (mcp_resource_wrapper, pilot resources). Plan: .cortex/plans/phase-43-reconsider-tools-registration.md.

- ✅ **Session optimization (2026-02-01): Require script-analysis when script run** - COMPLETE (2026-02-02) - Commit prompt: "Script use (MANDATORY)" step and "Script run without analysis" in COMMON ERRORS; agent-workflow (Synapse rule) script-use rule; integration tests added. Plan: .cortex/plans/session-optimization-commit-require-script-analysis.md.

- ✅ **Session optimization (2026-02-01): Connection closed handling** - COMPLETE (2026-02-01) - "Connection Closed During Long Tool (Retry Then Fallback)" in commit prompt; exception in MCP Tool Failure; docs/mcp-tool-timeouts.md "Client connection closed during long tools" subsection; optional Step 12.6 narrower scope for fix_markdown_lint.

- ✅ **Commit (2026-02-01)**: Pre-commit pipeline; fix ensure_usage_context when get_managers returns dict (mcp_stability accepts dict or Pydantic model). Phase 35 and Phase 36 plans archived. fix_errors, format, markdown lint, type_check, quality, tests 3309, coverage 90.42%.

- ✅ **Phase 42: Investigate execute_pre_commit_checks JSON error (commit 20260117)** - COMPLETE (2026-02-01) - Resolved by Phase 33 and Phase 35; plan archived to .cortex/plans/archive/Phase42/.

- ✅ **Phase 36: Enforce MCP tool failure protocol** - COMPLETE (2026-02-01) - Integrated MCPToolFailureHandler with mcp_tool_wrapper in mcp_stability.py; handle_tool_exception_if_failure runs on exception; creates investigation plan, adds to roadmap, raises MCPToolFailure when detect_failure is True. Unit test test_wrapper_invokes_failure_handler_on_json_error. Quality gate passes.

- ✅ **Commit (2026-02-01)**: Phase 35 plan archived; pre-commit pipeline (fix_errors, format, markdown lint 3 files, type_check, quality, tests 3308, coverage 90.34%).

- ✅ **Commit (2026-02-01)**: Pre-commit pipeline; markdown lint 5 files fixed (activeContext, progress, roadmap, phase-34, docs/mcp-tool-timeouts). fix_errors, format, type_check, quality, tests 3304, coverage 90.35%. Plan archiving in Step 7.

- ✅ **Phase 34: Ensure MCP tool timeouts** - COMPLETE (2026-02-01) - All tools had @mcp_tool_wrapper; synapse_repository uses asyncio.timeout; docs updated; verification test added. Quality gate passes.

- ✅ **Phase 33: Fix execute_pre_commit_checks JSON parsing error** - COMPLETE (2026-02-01) - Tool returns dict (ModelDict) so FastMCP serializes once; create_error_result_dict, unsupported_language_result_dict; _run_quality_checks uses dict directly. 3303 tests; quality gate passes.

- ✅ **Phase 32: Fix MCP tool connection closure errors** - COMPLETE (2026-02-01) - Pre-execution and before-retry health checks; connection state tracking; ConnectionError on connection failures; 3303 tests; coverage 90.38%; quality gate passes.

- ✅ **Phase 31: Fix optimize-context stale file errors** - COMPLETE (2026-02-01) - Existence check before read in load_context and load_progressive_context paths; read_file raises FileNotFoundError immediately (no retries). 3301 tests; coverage 90.39%; quality gate passes.

- ✅ **Phase 21: Health-Check and Optimization Analysis** - COMPLETE (2026-02-01) - Steps 6–9 done: CLI scripts/health_check.py; CI health-check step and artifact in .github/workflows/quality.yml; tests/tools/test_health_check_cli.py; docs/guides/health-check.md, docs/api/health-check.md, docs/api/tools.md (54 tools). Steps 2–4 implemented in module. All 3204 tests pass; coverage 90.83%.

- ✅ **Phase 20: Code Review Fixes** - COMPLETE (2026-02-01) - All steps done. Step 3.6 (initialization.py 188 lines) and 3.7 (structure_analyzer.py 264 lines) complete. All 10 file splits done; 3201 tests pass; quality gate passes. Plan: .cortex/plans/archive/Phase20/phase-20-code-review-fixes.md.

- ✅ **Phase 29: Track MCP tool usage** - COMPLETE (2026-02-01) - Usage tracking (UsageTracker, usage_models, usage_context); recording in mcp_stability; usage_analytics MCP tools; config usage_tracking.json. 3298 tests; coverage 90.27%; quality gate passes.

- ✅ **Phase 27: Script generation prevention** - COMPLETE (2026-02-01) - Steps 3–5, 7 done: script_promotion, discovery; script_capture_tools extended; implement prompt script-generation-prevention note. 3283 tests; coverage 90.84%.

### Recently Completed

- Commit (2026-02-02): Pre-commit pipeline; markdown lint 5 files fixed; 3311 tests, coverage 90.42%; 0 plans archived.
- Phase 43 Step 2 (Design Resource API): Design complete (2026-02-02) — phase-43-resource-api-design.md; URI cortex://, mcp_resource_wrapper, handler_kind, hybrid split.
- Phase 43 Step 1 (Audit): Tool audit complete (2026-02-02) — phase-43-tool-audit.md; 45 tools (28 Resource, 13 Tool, 4 Hybrid); MCP SDK mcp.resource() verified.
- Session optimization (2026-02-01): Require script-analysis when script run (2026-02-02).
- Phase 36: Enforce MCP tool failure protocol (2026-02-01).

## Project Health

- **Tests**: 3311+ passing; coverage ≥ 90%.
- **Linting/Types**: Pyright 0 errors, 0 warnings.
- **Quality**: File size and function length gates passing; all 10 Phase 20 file splits ≤400 lines.
- **Pre-commit adapters**: Python, TypeScript, JavaScript, Rust, Go, Java, Kotlin, Swift full implementations.
- **Health-check**: CLI scripts/health_check.py; CI step in quality.yml; analyze_health_check MCP tool.
- **Script capture**: capture_session_script, list_session_scripts, analyze_session_scripts, suggest_tool_improvements, promote_session_script MCP tools; script_promotion and discovery modules; .cortex/script-capture/ storage.
- **MCP tool failure protocol**: mcp_tool_wrapper invokes MCPToolFailureHandler on detected failures (JSON, connection, unexpected behavior); investigation plan created, roadmap updated, MCPToolFailure raised.
- **Plans**: Plans directory in sync with roadmap.
- **Path resolution**: Use Cortex MCP tools (`get_structure_info()`, `manage_file()`, `rules()`) for memory bank and structure paths.

## Next Focus

- **Phase 43 Step 3**: Implement Resources (mcp_resource_wrapper in mcp_stability.py; extend usage tracking with handler_kind; pilot resources get_memory_bank_stats, get_structure_info). Plan: .cortex/plans/phase-43-reconsider-tools-registration.md. Design: .cortex/plans/phase-43-resource-api-design.md.
