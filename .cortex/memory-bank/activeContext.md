# Active Context: Cortex

## Current Focus (2026-02-02)

See [roadmap.md](roadmap.md) for current status and milestones.

### Active Work

- **Phase 43: Reconsider tools registration (Step 3.2 partial complete)** (2026-02-02) - Step 3.1 done; pilot resources cortex://memory-bank/stats, cortex://structure/info. Step 3.2 Phase 1 foundation done: get_dependency_graph_resource, get_version_history_resource. Step 3.2 Phase 2 linking done: parse_file_links_resource (cortex://links/parse/{file_name}), resolve_transclusions_resource (cortex://links/transclusions/{file_name}), validate_links_resource (cortex://links/validate), get_link_graph_resource (cortex://links/graph). Next: manage_file read → Resource. Plan: .cortex/plans/phase-43-reconsider-tools-registration.md.

- **Commit (2026-02-02)**: Pre-commit pipeline; markdown lint 7 files fixed; tests 3320, coverage 90.44%; plan session-optimization-commit-rules-and-fallback archived (duplicate removed from plans/).

- ✅ **Session optimization (2026-02-02): Commit rules load and Step 12.6 fallback** - COMPLETE (2026-02-02) - Commit prompt: rules disabled → explicit rule file read; Step 12.6 and Connection Closed fallback: example markdownlint-cli2 command; docs/mcp-tool-timeouts.md and commit prompt: tool unavailability after connection closed. Integration tests added. Plan: .cortex/plans/archive/SessionOptimization/session-optimization-commit-rules-and-fallback-2026-02-02.md.

- ✅ **Session optimization (2026-02-01): Require script-analysis when script run** - COMPLETE (2026-02-02) - Commit prompt: "Script use (MANDATORY)" step and "Script run without analysis" in COMMON ERRORS; agent-workflow (Synapse rule) script-use rule; integration tests added. Plan: .cortex/plans/archive/SessionOptimization/session-optimization-commit-require-script-analysis.md.

- ✅ **Session optimization (2026-02-01): Connection closed handling** - COMPLETE (2026-02-01) - "Connection Closed During Long Tool (Retry Then Fallback)" in commit prompt; exception in MCP Tool Failure; docs/mcp-tool-timeouts.md "Client connection closed during long tools" subsection; optional Step 12.6 narrower scope for fix_markdown_lint.

- ✅ **Phase 43 Step 2 (Design Resource API)** - COMPLETE (2026-02-02) - Design: .cortex/plans/archive/Phase43/phase-43-resource-api-design.md; URI cortex://, mcp_resource_wrapper, handler_kind, hybrid split.

- ✅ **Phase 43 Step 1 (Audit)** - COMPLETE (2026-02-02) - .cortex/plans/archive/Phase43/phase-43-tool-audit.md; 45 tools (28 Resource, 13 Tool, 4 Hybrid); MCP SDK mcp.resource() verified.

### Recently Completed

- Commit (2026-02-02): Pre-commit pipeline; markdown lint 7 files fixed; tests 3320, coverage 90.44%; duplicate session-optimization plan removed from plans/ (already in archive).
- Session optimization (2026-02-02): Commit rules load and Step 12.6 fallback; rules disabled → explicit rule file read; markdown lint fallback example; tool unavailability after connection closed; integration tests; plan archived.
- Phase 43 Step 3.2 (Phase 2 linking): parse_file_links_resource, resolve_transclusions_resource, validate_links_resource, get_link_graph_resource; unit tests in test_phase2_linking.py; plan and roadmap updated; 37 Phase 2 linking tests pass; quality gate passes.
- Phase 43 Step 3.2 (Phase 1 foundation): get_dependency_graph_resource, get_version_history_resource; unit tests; plan and roadmap updated; 3312 tests pass; quality gate passes.
- Phase 43 Step 3 (partial): mcp_resource_wrapper, handler_kind, pilot resources cortex://memory-bank/stats and cortex://structure/info; verification test; 3312 tests pass; quality gate passes.
- Phase 43 Step 2 (Design Resource API): Design complete (2026-02-02).
- Phase 43 Step 1 (Audit): Tool audit complete (2026-02-02).

## Project Health

- **Tests**: 3320+ passing; coverage ≥ 90%.
- **Linting/Types**: Pyright 0 errors, 0 warnings.
- **Quality**: File size and function length gates passing; all 10 Phase 20 file splits ≤400 lines.
- **Pre-commit adapters**: Python, TypeScript, JavaScript, Rust, Go, Java, Kotlin, Swift full implementations.
- **Health-check**: CLI scripts/health_check.py; CI step in quality.yml; analyze_health_check MCP tool.
- **Script capture**: capture_session_script, list_session_scripts, analyze_session_scripts, suggest_tool_improvements, promote_session_script MCP tools; script_promotion and discovery modules; .cortex/script-capture/ storage.
- **MCP tool failure protocol**: mcp_tool_wrapper invokes MCPToolFailureHandler on detected failures; investigation plan created, roadmap updated, MCPToolFailure raised.
- **MCP resources (Phase 43)**: mcp_resource_wrapper; handler_kind in usage events; resources cortex://memory-bank/stats, cortex://structure/info, cortex://memory-bank/dependency-graph, cortex://memory-bank/version-history/{file_name}, cortex://links/parse/{file_name}, cortex://links/transclusions/{file_name}, cortex://links/validate, cortex://links/graph; verification test for resource decorator stack.
- **Plans**: Plans directory in sync with roadmap.
- **Path resolution**: Use Cortex MCP tools (`get_structure_info()`, `manage_file()`, `rules()`) for memory bank and structure paths.

## Next Focus

- **Phase 43 Step 3.2**: manage_file read → Resource; then Phase 3 Validation, Phase 4 Optimization, etc. Plan: .cortex/plans/phase-43-reconsider-tools-registration.md.
