# Active Context: Cortex

## Current Focus (2026-02-02)

See [roadmap.md](roadmap.md) for current status and milestones.

### Active Work

- ✅ **Fix commit workflow: re-run Step 12.3 after code fixes in Step 12** - COMPLETE (2026-02-02) - Commit prompt requires re-run of Step 12.3 after fixes in 12.2/12.3; E402 reminder; Step 13 precondition; integration test. Blocker resolved.

- **Phase 45: Add MCP annotations (IN PROGRESS)** (2026-02-02) - Phases 1–3 done: mcp_annotations.py helpers and unit tests; annotations on manage_file, get_memory_bank_stats, validate, analyze, configure, get_version_history, rollback_file_version, check_structure_health, get_structure_info, check_mcp_connection_health, execute_pre_commit_checks, fix_quality_issues. Next: remaining tools (rules, markdown, synapse, phase4/phase5/linking/refactoring); resolve type_check for `annotations` (stub or CI). Plan: .cortex/plans/phase-45-add-mcp-annotations.md.

- **Phase 43: Reconsider tools registration (Step 3.2 partial complete)** (2026-02-02) - Step 3.1 done; pilot resources cortex://memory-bank/stats, cortex://structure/info. Step 3.2 Phase 1–4 done (foundation, linking, validation, optimization resources). Next: Phase 5 Analysis, etc. Plan: .cortex/plans/phase-43-reconsider-tools-registration.md.

- ✅ **Phase 48: Improve optimize-context feedback** - COMPLETE (2026-02-02) - analyze-context-effectiveness.md enhanced with Pre-Analysis Checklist, Usage Analysis, Scoring Metrics, Feedback Categories, Feedback Schema; manifest entry; integration tests test_analyze_context_effectiveness_prompt.

- ✅ **Phase 47: Add prompt icons and emoji in messages** - COMPLETE (2026-02-02) - Icon helper (create_emoji_icon, create_emoji_icons); PROMPT_ICONS and icons on setup prompts; SYNAPSE_PROMPT_ICONS and icons in synapse_prompts; optional manifest icon; ✅ in manage_file and get_structure_info messages. Quality gate passes.

- ✅ **Phase 46: Extract setup to separate MCP server** - COMPLETE (2026-02-02) - Setup prompts in cortex.setup.prompts; should_mount_setup in cortex.setup; main.py imports setup.prompts; tests updated to cortex.setup.prompts; quality gate passes.

- ✅ **Phase 46: Add progress reporting** - COMPLETE (2026-02-02) - ProgressReporter, mcp_tool_wrapper(enable_progress=...), time-based progress loop; unit tests; quality gate passes.

- ✅ **Session optimization (2026-02-02): Commit rules load and Step 12.6 fallback** - COMPLETE (2026-02-02).

- ✅ **Session optimization (2026-02-01): Require script-analysis when script run** - COMPLETE (2026-02-02).

- ✅ **Session optimization (2026-02-01): Connection closed handling** - COMPLETE (2026-02-01).

- ✅ **Phase 43 Step 2 (Design Resource API)** - COMPLETE (2026-02-02).

- ✅ **Phase 43 Step 1 (Audit)** - COMPLETE (2026-02-02).

### Recently Completed

- Phase 48 (2026-02-02): analyze-context-effectiveness prompt enhanced (Pre-Analysis Checklist, Usage Analysis, Scoring Metrics, Feedback Categories, Feedback Schema); manifest entry; integration tests test_analyze_context_effectiveness_prompt.
- Phase 47 (2026-02-02): Icon helper (icon_helpers.py); emoji icons on all setup and Synapse prompts; optional manifest icon; ✅ in manage_file write message and get_structure_info message; unit tests; quality gate passes.
- Commit (2026-02-02): Quality gate fixes—pre_commit_tools under 400 lines via pre_commit_pipeline.py; function length fixes in pre_commit_tools and python_adapter.
- Phase 46: ProgressReporter (src/cortex/core/progress.py); mcp_tool_wrapper enable_progress (auto when timeout ≥ 120s); time-based progress loop; unit tests; quality gate passes.
- Phase 45 (partial): mcp_annotations.py helpers; annotations on 12 MCP tools.
- Phase 43 Step 3.2 (Phase 4 Optimization): load_context_resource, load_progressive_context_resource, get_relevance_scores_resource, summarize_content_resource; unit tests; quality gate passes.

## Project Health

- **Tests**: 3354+ passing; coverage ≥ 90%.
- **Linting/Types**: Pyright 0 errors, 0 warnings.
- **Quality**: File size and function length gates passing; pre_commit_tools <400 lines (pipeline in pre_commit_pipeline.py).
- **Pre-commit adapters**: Python, TypeScript, JavaScript, Rust, Go, Java, Kotlin, Swift full implementations.
- **Health-check**: CLI scripts/health_check.py; CI step in quality.yml; analyze_health_check MCP tool.
- **Script capture**: capture_session_script, list_session_scripts, analyze_session_scripts, suggest_tool_improvements, promote_session_script MCP tools; script_promotion and discovery modules; .cortex/script-capture/ storage.
- **MCP tool failure protocol**: mcp_tool_wrapper invokes MCPToolFailureHandler on detected failures; investigation plan created, roadmap updated, MCPToolFailure raised.
- **Progress reporting (Phase 46)**: ProgressReporter for stage-based progress; mcp_tool_wrapper(enable_progress=None) auto-enables for timeout ≥ 120s; time-based progress every 10s when ctx present; PROGRESS_REPORT_INTERVAL_SECONDS, PROGRESS_THRESHOLD_TIMEOUT_SECONDS.
- **MCP resources (Phase 43)**: mcp_resource_wrapper; handler_kind in usage events; resources cortex://memory-bank/stats, cortex://structure/info, cortex://memory-bank/dependency-graph, cortex://memory-bank/version-history/{file_name}, cortex://links/_, cortex://memory-bank/file/{file_name}, cortex://validation/validate/{check_type}, cortex://optimization/_; verification test for resource decorator stack.
- **MCP annotations (Phase 45)**: ToolAnnotations Pydantic model; helpers read_only_annotations, safe_write_annotations, destructive_annotations, external_annotations; annotations on 12 tools.
- **Prompt icons (Phase 47)**: create_emoji_icon/create_emoji_icons in icon_helpers.py; emoji icons on setup and Synapse prompts; optional manifest icon; ✅ in manage_file and get_structure_info success messages.
- **Plans**: Plans directory in sync with roadmap.
- **Path resolution**: Use Cortex MCP tools (`get_structure_info()`, `manage_file()`, `rules()`) for memory bank and structure paths.

## Next Focus

- **Phase 45**: Add annotations to remaining MCP tools (rules, markdown, synapse, phase4/phase5/linking/refactoring); docs and type_check resolution. Plan: .cortex/plans/phase-45-add-mcp-annotations.md.
- **Phase 43 Step 3.2**: Phase 5 Analysis (analyze, suggest_refactoring, get_refactoring_suggestions), etc. Plan: .cortex/plans/phase-43-reconsider-tools-registration.md.
