# Active Context: Cortex

## Current Focus (2026-02-02)

See [roadmap.md](roadmap.md) for current status and milestones.

### Active Work

- **Phase 45: Add MCP annotations (IN PROGRESS)** (2026-02-02) - Phases 1–3 done: mcp_annotations.py helpers and unit tests; annotations on manage_file, get_memory_bank_stats, validate, analyze, configure, get_version_history, rollback_file_version, check_structure_health, get_structure_info, check_mcp_connection_health, execute_pre_commit_checks, fix_quality_issues. Next: remaining tools (rules, markdown, synapse, phase4/phase5/linking/refactoring); resolve type_check for `annotations` (stub or CI). Plan: .cortex/plans/phase-45-add-mcp-annotations.md.

- **Commit (2026-02-02)**: Pre-commit pipeline; fix_errors, format, markdown lint 0 files fixed; type_check, quality, tests 3343, coverage 90.47%; Phase 45 MCP annotations partial.

- **Phase 43: Reconsider tools registration (Step 3.2 partial complete)** (2026-02-02) - Step 3.1 done; pilot resources cortex://memory-bank/stats, cortex://structure/info. Step 3.2 Phase 1 foundation done: get_dependency_graph_resource, get_version_history_resource. Step 3.2 Phase 2 linking done: parse_file_links_resource, resolve_transclusions_resource, validate_links_resource, get_link_graph_resource. manage_file read done: get_file_resource (cortex://memory-bank/file/{file_name}). Step 3.2 Phase 3 validation done: validate_resource (cortex://validation/validate/{check_type}). Step 3.2 Phase 4 Optimization done (2026-02-02): load_context_resource (cortex://optimization/load-context/{task_description}), load_progressive_context_resource (cortex://optimization/load-progressive-context/{task_description}), get_relevance_scores_resource (cortex://optimization/relevance-scores/{task_description}), summarize_content_resource (cortex://optimization/summarize/{file_name}). Next: Phase 5 Analysis, etc. Plan: .cortex/plans/phase-43-reconsider-tools-registration.md.

- ✅ **Session optimization (2026-02-02): Commit rules load and Step 12.6 fallback** - COMPLETE (2026-02-02) - Commit prompt: rules disabled → explicit rule file read; Step 12.6 and Connection Closed fallback: example markdownlint-cli2 command; docs/mcp-tool-timeouts.md and commit prompt: tool unavailability after connection closed. Integration tests added. Plan: .cortex/plans/archive/SessionOptimization/session-optimization-commit-rules-and-fallback-2026-02-02.md.

- ✅ **Session optimization (2026-02-01): Require script-analysis when script run** - COMPLETE (2026-02-02) - Commit prompt: "Script use (MANDATORY)" step and "Script run without analysis" in COMMON ERRORS; agent-workflow (Synapse rule) script-use rule; integration tests added. Plan: .cortex/plans/archive/SessionOptimization/session-optimization-commit-require-script-analysis.md.

- ✅ **Session optimization (2026-02-01): Connection closed handling** - COMPLETE (2026-02-01) - "Connection Closed During Long Tool (Retry Then Fallback)" in commit prompt; exception in MCP Tool Failure; docs/mcp-tool-timeouts.md "Client connection closed during long tools" subsection; optional Step 12.6 narrower scope for fix_markdown_lint.

- ✅ **Phase 43 Step 2 (Design Resource API)** - COMPLETE (2026-02-02) - Design: .cortex/plans/archive/Phase43/phase-43-resource-api-design.md; URI cortex://, mcp_resource_wrapper, handler_kind, hybrid split.

- ✅ **Phase 43 Step 1 (Audit)** - COMPLETE (2026-02-02) - .cortex/plans/archive/Phase43/phase-43-tool-audit.md; 45 tools (28 Resource, 13 Tool, 4 Hybrid); MCP SDK mcp.resource() verified.

### Recently Completed

- Phase 45 (partial): mcp_annotations.py helpers (read_only_annotations, safe_write_annotations, destructive_annotations, external_annotations); unit tests; annotations added to 12 MCP tools.
- Commit (2026-02-02): Pre-commit pipeline; markdown lint 4 files fixed; tests 3331, coverage 90.46%; 0 plans archived.
- Phase 43 Step 3.2 (Phase 4 Optimization): load_context_resource, load_progressive_context_resource, get_relevance_scores_resource, summarize_content_resource; URL-decode path params; unit tests TestPhase4OptimizationResources; plan and roadmap updated; quality gate passes.

## Project Health

- **Tests**: 3343 passing; coverage ≥ 90%.
- **Linting/Types**: Pyright 0 errors, 0 warnings.
- **Quality**: File size and function length gates passing; all 10 Phase 20 file splits ≤400 lines.
- **Pre-commit adapters**: Python, TypeScript, JavaScript, Rust, Go, Java, Kotlin, Swift full implementations.
- **Health-check**: CLI scripts/health_check.py; CI step in quality.yml; analyze_health_check MCP tool.
- **Script capture**: capture_session_script, list_session_scripts, analyze_session_scripts, suggest_tool_improvements, promote_session_script MCP tools; script_promotion and discovery modules; .cortex/script-capture/ storage.
- **MCP tool failure protocol**: mcp_tool_wrapper invokes MCPToolFailureHandler on detected failures; investigation plan created, roadmap updated, MCPToolFailure raised.
- **MCP resources (Phase 43)**: mcp_resource_wrapper; handler_kind in usage events; resources cortex://memory-bank/stats, cortex://structure/info, cortex://memory-bank/dependency-graph, cortex://memory-bank/version-history/{file_name}, cortex://links/parse/{file_name}, cortex://links/transclusions/{file_name}, cortex://links/validate, cortex://links/graph, cortex://memory-bank/file/{file_name} (get_file_resource), cortex://validation/validate/{check_type} (validate_resource), cortex://optimization/load-context/{task_description} (load_context_resource), cortex://optimization/load-progressive-context/{task_description} (load_progressive_context_resource), cortex://optimization/relevance-scores/{task_description} (get_relevance_scores_resource), cortex://optimization/summarize/{file_name} (summarize_content_resource); verification test for resource decorator stack.
- **MCP annotations (Phase 45)**: ToolAnnotations Pydantic model; helpers read_only_annotations, safe_write_annotations, destructive_annotations, external_annotations; annotations added to 12 tools (manage_file, get_memory_bank_stats, validate, analyze, configure, get_version_history, rollback_file_version, check_structure_health, get_structure_info, check_mcp_connection_health, execute_pre_commit_checks, fix_quality_issues).
- **Plans**: Plans directory in sync with roadmap.
- **Path resolution**: Use Cortex MCP tools (`get_structure_info()`, `manage_file()`, `rules()`) for memory bank and structure paths.

## Next Focus

- **Phase 45**: Add annotations to remaining MCP tools (rules, markdown, synapse, phase4/phase5/linking/refactoring); docs and type_check resolution. Plan: .cortex/plans/phase-45-add-mcp-annotations.md.
- **Phase 43 Step 3.2**: Phase 5 Analysis (analyze, suggest_refactoring, get_refactoring_suggestions), etc. Plan: .cortex/plans/phase-43-reconsider-tools-registration.md.
