# Active Context: Cortex

## Current Focus (2026-02-02)

See [roadmap.md](roadmap.md) for current status and milestones.

### Active Work

- **Phase 43: Reconsider tools registration (Step 3.2 partial complete)** (2026-02-02) - Step 3.1 done; pilot resources cortex://memory-bank/stats, cortex://structure/info. Step 3.2 Phase 1 foundation done: get_dependency_graph_resource, get_version_history_resource. Step 3.2 Phase 2 linking done: parse_file_links_resource, resolve_transclusions_resource, validate_links_resource, get_link_graph_resource. manage_file read done: get_file_resource (cortex://memory-bank/file/{file_name}). Step 3.2 Phase 3 validation done: validate_resource (cortex://validation/validate/{check_type}). Step 3.2 Phase 4 Optimization done (2026-02-02): load_context_resource (cortex://optimization/load-context/{task_description}), load_progressive_context_resource (cortex://optimization/load-progressive-context/{task_description}), get_relevance_scores_resource (cortex://optimization/relevance-scores/{task_description}), summarize_content_resource (cortex://optimization/summarize/{file_name}). Next: Phase 5 Analysis, etc. Plan: .cortex/plans/phase-43-reconsider-tools-registration.md.

- **Commit (2026-02-02)**: Pre-commit pipeline; markdown lint 0 files fixed; tests 3326, coverage 90.45%; 0 plans archived. Changes: mcp_stability, main (connection error handling), test_main_error_handling.

- **Commit (2026-02-02)**: Pre-commit pipeline; markdown lint 4 files fixed; tests 3323, coverage 90.45%; 0 plans archived.

- ✅ **Session optimization (2026-02-02): Commit rules load and Step 12.6 fallback** - COMPLETE (2026-02-02) - Commit prompt: rules disabled → explicit rule file read; Step 12.6 and Connection Closed fallback: example markdownlint-cli2 command; docs/mcp-tool-timeouts.md and commit prompt: tool unavailability after connection closed. Integration tests added. Plan: .cortex/plans/archive/SessionOptimization/session-optimization-commit-rules-and-fallback-2026-02-02.md.

- ✅ **Session optimization (2026-02-01): Require script-analysis when script run** - COMPLETE (2026-02-02) - Commit prompt: "Script use (MANDATORY)" step and "Script run without analysis" in COMMON ERRORS; agent-workflow (Synapse rule) script-use rule; integration tests added. Plan: .cortex/plans/archive/SessionOptimization/session-optimization-commit-require-script-analysis.md.

- ✅ **Session optimization (2026-02-01): Connection closed handling** - COMPLETE (2026-02-01) - "Connection Closed During Long Tool (Retry Then Fallback)" in commit prompt; exception in MCP Tool Failure; docs/mcp-tool-timeouts.md "Client connection closed during long tools" subsection; optional Step 12.6 narrower scope for fix_markdown_lint.

- ✅ **Phase 43 Step 2 (Design Resource API)** - COMPLETE (2026-02-02) - Design: .cortex/plans/archive/Phase43/phase-43-resource-api-design.md; URI cortex://, mcp_resource_wrapper, handler_kind, hybrid split.

- ✅ **Phase 43 Step 1 (Audit)** - COMPLETE (2026-02-02) - .cortex/plans/archive/Phase43/phase-43-tool-audit.md; 45 tools (28 Resource, 13 Tool, 4 Hybrid); MCP SDK mcp.resource() verified.

### Recently Completed

- Phase 43 Step 3.2 (Phase 4 Optimization): load_context_resource, load_progressive_context_resource, get_relevance_scores_resource, summarize_content_resource; URL-decode path params; unit tests TestPhase4OptimizationResources; plan and roadmap updated; quality gate passes.
- Commit (2026-02-02): Pre-commit pipeline; markdown lint 4 files fixed; tests 3321, coverage 90.45%; 0 plans archived.
- Phase 43 Step 3.2 (Phase 3 validation): validate_resource; unit tests; plan and roadmap updated; 3323 tests pass; quality gate passes.
- Phase 43 Step 3.2 (manage_file read): get_file_resource; unit test; plan and roadmap updated; 3321 tests pass; quality gate passes.
- Phase 43 Step 3.2 (Phase 2 linking): parse_file_links_resource, resolve_transclusions_resource, validate_links_resource, get_link_graph_resource; unit tests in test_phase2_linking.py; plan and roadmap updated; 37 Phase 2 linking tests pass; quality gate passes.
- Phase 43 Step 3.2 (Phase 1 foundation): get_dependency_graph_resource, get_version_history_resource; unit tests; plan and roadmap updated; 3312 tests pass; quality gate passes.
- Phase 43 Step 3 (partial): mcp_resource_wrapper, handler_kind, pilot resources cortex://memory-bank/stats and cortex://structure/info; verification test; 3312 tests pass; quality gate passes.
- Phase 43 Step 2 (Design Resource API): Design complete (2026-02-02).
- Phase 43 Step 1 (Audit): Tool audit complete (2026-02-02).

## Project Health

- **Tests**: 3321+ passing; coverage ≥ 90%.
- **Linting/Types**: Pyright 0 errors, 0 warnings.
- **Quality**: File size and function length gates passing; all 10 Phase 20 file splits ≤400 lines.
- **Pre-commit adapters**: Python, TypeScript, JavaScript, Rust, Go, Java, Kotlin, Swift full implementations.
- **Health-check**: CLI scripts/health_check.py; CI step in quality.yml; analyze_health_check MCP tool.
- **Script capture**: capture_session_script, list_session_scripts, analyze_session_scripts, suggest_tool_improvements, promote_session_script MCP tools; script_promotion and discovery modules; .cortex/script-capture/ storage.
- **MCP tool failure protocol**: mcp_tool_wrapper invokes MCPToolFailureHandler on detected failures; investigation plan created, roadmap updated, MCPToolFailure raised.
- **MCP resources (Phase 43)**: mcp_resource_wrapper; handler_kind in usage events; resources cortex://memory-bank/stats, cortex://structure/info, cortex://memory-bank/dependency-graph, cortex://memory-bank/version-history/{file_name}, cortex://links/parse/{file_name}, cortex://links/transclusions/{file_name}, cortex://links/validate, cortex://links/graph, cortex://memory-bank/file/{file_name} (get_file_resource), cortex://validation/validate/{check_type} (validate_resource), cortex://optimization/load-context/{task_description} (load_context_resource), cortex://optimization/load-progressive-context/{task_description} (load_progressive_context_resource), cortex://optimization/relevance-scores/{task_description} (get_relevance_scores_resource), cortex://optimization/summarize/{file_name} (summarize_content_resource); verification test for resource decorator stack.
- **Plans**: Plans directory in sync with roadmap.
- **Path resolution**: Use Cortex MCP tools (`get_structure_info()`, `manage_file()`, `rules()`) for memory bank and structure paths.

## Next Focus

- **Phase 43 Step 3.2**: Phase 5 Analysis (analyze, suggest_refactoring, get_refactoring_suggestions), etc. Plan: .cortex/plans/phase-43-reconsider-tools-registration.md.
