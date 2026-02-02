# Active Context: Cortex

## Current Focus (2026-02-02)

See [roadmap.md](roadmap.md) for current status and milestones.

### Active Work

- ✅ **Merge analyze* prompts into single end-of-session analyze (Blocker)** - COMPLETE (2026-02-02) - Unified `analyze.md` prompt; manifest and SYNAPSE_PROMPT_ICONS updated; old prompts archived; integration tests assert on unified analyze; README updated. Blocker resolved.

- **Phase 45: Add MCP annotations (IN PROGRESS)** (2026-02-02) - Phases 1–3 done: mcp_annotations.py helpers and unit tests; annotations on manage_file, get_memory_bank_stats, validate, analyze, configure, get_version_history, rollback_file_version, check_structure_health, get_structure_info, check_mcp_connection_health, execute_pre_commit_checks, fix_quality_issues. Next: remaining tools (rules, markdown, synapse, phase4/phase5/linking/refactoring); resolve type_check for `annotations` (stub or CI). Plan: .cortex/plans/phase-45-add-mcp-annotations.md.

- **Phase 43: Reconsider tools registration (Step 3.2 context/health/scripts/usage done)** (2026-02-02) - Step 3.1 done; Step 3.2 Phase 1–5, structure/synapse/rules, and context/health/scripts/usage done. New resources: analyze_context_effectiveness_resource (cortex://optimization/context-effectiveness), get_context_usage_statistics_resource (cortex://optimization/context-usage-statistics), check_mcp_connection_health_resource (cortex://health/connection), analyze_health_check_resource (cortex://health/analyze/{analysis_type}), list_session_scripts_resource (cortex://scripts/list), analyze_session_scripts_resource (cortex://scripts/analyze), suggest_tool_improvements_resource (cortex://scripts/suggest-improvements/{task_description}), get_tool_usage_stats_resource (cortex://usage/stats), get_unused_tools_resource (cortex://usage/unused), get_tool_usage_report_resource (cortex://usage/report), get_optimization_recommendations_resource (cortex://usage/optimization-recommendations). Unit tests in test_context_analysis_handlers, test_connection_health, test_health_check_operations, test_script_capture_tools, test_usage_analytics. Next: Step 3.3 (hybrid operations) or Step 3.4 (update tool registrations). Plan: .cortex/plans/phase-43-reconsider-tools-registration.md.

- ✅ **Phase 48: Optimize-context feedback analysis** - COMPLETE (2026-02-02) - Marked complete; implementation delivered by Phase 48 Improve optimize-context feedback. Plan archived to .cortex/plans/archive/Phase48/phase-48-optimize-context-feedback-analysis.md.

- ✅ **Phase 48: Improve optimize-context feedback** - COMPLETE (2026-02-02) - Replaced by unified Analyze prompt (analyze.md); former analyze-context-effectiveness and analyze-session-optimization archived.

- ✅ **Phase 47: Add prompt icons and emoji in messages** - COMPLETE (2026-02-02) - Icon helper (create_emoji_icon, create_emoji_icons); PROMPT_ICONS and icons on setup prompts; SYNAPSE_PROMPT_ICONS and icons in synapse_prompts; optional manifest icon; ✅ in manage_file and get_structure_info messages. Quality gate passes.

- ✅ **Phase 46: Extract setup to separate MCP server** - COMPLETE (2026-02-02) - Setup prompts in cortex.setup.prompts; should_mount_setup in cortex.setup; main.py imports setup.prompts; tests updated to cortex.setup.prompts; quality gate passes.

- ✅ **Phase 46: Add progress reporting** - COMPLETE (2026-02-02) - ProgressReporter, mcp_tool_wrapper(enable_progress=...); time-based progress loop; unit tests; quality gate passes.

- ✅ **Session optimization (2026-02-02): Commit rules load and Step 12.6 fallback** - COMPLETE (2026-02-02).

- ✅ **Session optimization (2026-02-01): Require script-analysis when script run** - COMPLETE (2026-02-02).

- ✅ **Session optimization (2026-02-01): Connection closed handling** - COMPLETE (2026-02-01).

- ✅ **Phase 43 Step 2 (Design Resource API)** - COMPLETE (2026-02-02).

- ✅ **Phase 43 Step 1 (Audit)** - COMPLETE (2026-02-02).

### Recently Completed

- Phase 43 Step 3.2 context/health/scripts/usage resources (2026-02-02): analyze_context_effectiveness_resource, get_context_usage_statistics_resource, check_mcp_connection_health_resource, analyze_health_check_resource, list_session_scripts_resource, analyze_session_scripts_resource, suggest_tool_improvements_resource, get_tool_usage_stats_resource, get_unused_tools_resource, get_tool_usage_report_resource, get_optimization_recommendations_resource; unit tests; test_usage_analytics.py; quality gate passes.
- Phase 43 Step 3.2 structure/synapse/rules resources (2026-02-02): check_structure_health_resource, rules_get_relevant_resource, get_synapse_rules_resource, get_synapse_prompts_resource; unit tests; quality gate passes.
- Merge analyze* prompts blocker (2026-02-02): Unified analyze.md; manifest and icons; old prompts archived; integration tests; README; quality gate passes.
- Phase 43 Step 3.2 Phase 5 Analysis (2026-02-02): analyze_resource (cortex://analysis/analyze/{target}), suggest_refactoring_resource (cortex://analysis/suggest-refactoring/{type}); unit tests TestAnalyzeResource, TestSuggestRefactoringResource; quality gate passes.
- Phase 48 Optimize-context feedback analysis (2026-02-02): Marked COMPLETE; plan archived to .cortex/plans/archive/Phase48/phase-48-optimize-context-feedback-analysis.md.
- Phase 48 (2026-02-02): Replaced by unified Analyze prompt (analyze.md); former analyze-context-effectiveness and analyze-session-optimization archived.
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
- **MCP resources (Phase 43)**: mcp_resource_wrapper; handler_kind in usage events; resources cortex://memory-bank/stats, cortex://structure/info, cortex://structure/health, cortex://memory-bank/dependency-graph, cortex://memory-bank/version-history/{file_name}, cortex://links/*, cortex://memory-bank/file/{file_name}, cortex://validation/validate/{check_type}, cortex://optimization/*, cortex://optimization/context-effectiveness, cortex://optimization/context-usage-statistics, cortex://analysis/analyze/{target}, cortex://analysis/suggest-refactoring/{type}, cortex://rules/relevant/{task_description}, cortex://synapse/rules/{task_description}, cortex://synapse/prompts, cortex://health/connection, cortex://health/analyze/{analysis_type}, cortex://scripts/list, cortex://scripts/analyze, cortex://scripts/suggest-improvements/{task_description}, cortex://usage/stats, cortex://usage/unused, cortex://usage/report, cortex://usage/optimization-recommendations; verification test for resource decorator stack.
- **MCP annotations (Phase 45)**: ToolAnnotations Pydantic model; helpers read_only_annotations, safe_write_annotations, destructive_annotations, external_annotations; annotations on 12 tools.
- **Prompt icons (Phase 47)**: create_emoji_icon/create_emoji_icons in icon_helpers.py; emoji icons on setup and Synapse prompts; optional manifest icon; ✅ in manage_file and get_structure_info success messages.
- **Unified Analyze prompt**: Single end-of-session prompt `analyze.md` (context effectiveness + session optimization); former analyze-context-effectiveness and analyze-session-optimization archived.
- **Plans**: Plans directory in sync with roadmap.
- **Path resolution**: Use Cortex MCP tools (`get_structure_info()`, `manage_file()`, `rules()`) for memory bank and structure paths.

## Next Focus

- **Phase 45**: Add annotations to remaining MCP tools (rules, markdown, synapse, phase4/phase5/linking/refactoring); docs and type_check resolution. Plan: .cortex/plans/phase-45-add-mcp-annotations.md.
- **Phase 43 Step 3.3/3.4**: Step 3.2 read-only resources done; next: Step 3.3 (hybrid operations) or Step 3.4 (update tool registrations). Plan: .cortex/plans/phase-43-reconsider-tools-registration.md.
