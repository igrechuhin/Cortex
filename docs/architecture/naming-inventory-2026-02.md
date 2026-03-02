# Naming Inventory (2026-02)

**Status**: Step 1 deliverable (plan: unify-simplify-tools-prompts-resources-naming)  
**Created**: 2026-02-27

## Purpose

Catalog current names for Cortex MCP tools, `cortex://` resources, and Synapse prompts. Identifies inconsistencies and altitude-rubric gaps for the unified naming plan.

## 1. Tools

**Source**: `src/cortex/tools/categories.py` (TOOL_CATEGORIES). Total: 37 tools.

### 1.1 By pattern

| Pattern | Tools | Notes |
|---------|-------|-------|
| `manage_*` | manage_file | Imperative; side effects. ✓ |
| `query_*` | query_memory_bank, query_usage | Read-only consolidated dispatchers. ✓ |
| `get_*` | get_structure_info, get_relevance_scores | Read-only; Phase 43: get_*only for read-only. Consider query_* or resource-only for consistency. |
| `*_file` | manage_file | ✓ |
| `append_*` | append_entry | Imperative; side effects. ✓ (consolidates append_progress_entry, append_active_context_entry) |
| `execute_*` | execute_pre_commit_checks | ✓ |
| `fix_*` | fix_quality_issues, fix_markdown_lint | Imperative. ✓ |
| `check_*` | check_mcp_connection_health, check_structure_health | Read-only checks. ✓ |
| `validate` | validate | Dispatcher; imperative. ✓ |
| `load_*` | load_context | Read-only; has resource. ✓ |
| `rules` | rules | Dispatcher; noun. Consider verb for consistency. |
| `plan` | plan | Dispatcher; noun. ✓ (consolidates create_plan, etc.) |
| `roadmap` | roadmap | Dispatcher; noun. ✓ |
| `analyze` | analyze, analyze_error_patterns | Mixed: analyze is dispatcher; analyze_error_patterns is specific. |
| `configure` | configure | Dispatcher. ✓ |
| `search_*` | search_tools | Read-only. ✓ |
| `session_*` | session, manage_session_scripts | session = lifecycle; manage_session_scripts = dispatcher. |
| `compact_*` | compact_session | Imperative. ✓ |
| `run_*` | run_composite_workflow | Dispatcher; run_* for composite workflows. ✓ |
| `rollback_*` | rollback_file_version | Imperative. ✓ |
| `update_*` / `sync_*` | synapse (operation=update_rule or update_prompt or sync) | Dispatcher; noun. ✓ |
| `run_*` | run_tool_evaluation | Imperative. ✓ |
| `benchmark_*` | benchmark_model | Imperative. ✓ |
| `suggest_*` | suggest_refactoring | Imperative (returns suggestions). ✓ |
| `apply_*` | apply_refactoring | Imperative. ✓ |
| `register_*` | register_plan_in_roadmap | Imperative. ✓ |
| `cleanup_*` | cleanup_metadata_index | Imperative. ✓ |
| `sequentialthinking`, `think` | — | CamelCase / lowercase; inconsistent casing. |

### 1.2 Inconsistencies

- **get_* vs query_***: `get_structure_info` and `get_relevance_scores` are read-only but use `get_*` instead of `query_*`. Phase 43/50 consolidated most reads into `query_memory_bank` and `query_usage`; these remain standalone.
- **Noun-only dispatchers**: `rules`, `plan`, `roadmap` are nouns; other dispatchers use verbs (configure, validate, analyze).
- **Casing**: `sequentialthinking` (lowercase) vs `session_start` (snake_case). `think` is short form.

### 1.3 Altitude rubric (to audit)

**Target** (from [tool-description-altitude-rubric.md](../guides/tool-description-altitude-rubric.md)): All tools score ≥4; 20+ tools with examples (score 5).

**Criteria**: Purpose, USE WHEN, input expectations, RETURNS, Examples (for score 5).

**Action**: Audit each tool's docstring against the rubric. Flag tools below score 4. Suggested tools to prioritize (high-use): manage_file, load_context, query_memory_bank, rules, execute_pre_commit_checks, get_structure_info, session_start, plan, roadmap.

## 2. Resources (cortex:// URIs)

**Source**: Grep `uri="cortex://` in `src/`. Total: 35 resource URIs.

### 2.1 By domain

| Domain | Paths | Hyphenation | Singular/Plural |
|--------|-------|-------------|-----------------|
| memory-bank | file/{file_name}, stats, dependency-graph, version-history/{file_name} | Mixed: dependency-graph ✓, version-history ✓ | file (singular) ✓ |
| optimization | load-context/{task}, relevance-scores/{task}, summarize/{file_name}, context-effectiveness, context-usage-statistics | hyphenated ✓ | load-context ✓ |
| links | parse/{file_name}, transclusions/{file_name}, validate, graph | hyphen-free for short paths | parse, graph (singular) ✓ |
| structure | info, health | ✓ | ✓ |
| project | root | ✓ | ✓ |
| analysis | analyze/{target}, suggest-refactoring/{type} | suggest-refactoring ✓ | ✓ |
| usage | stats, unused, report, optimization-recommendations, observation/{id} | optimization-recommendations ✓ | ✓ |
| synapse | rules/{task}, prompts | ✓ | rules, prompts (plural) |
| validation | validate/{check_type} | ✓ | ✓ |
| health | connection, analyze/{analysis_type} | ✓ | ✓ |
| scripts | list, analyze, suggest-improvements/{task} | suggest-improvements ✓ | ✓ |
| rules | relevant/{task_description} | ✓ | Overlaps with synapse/rules. |
| config | {component} | ✓ | ✓ |

### 2.2 Inconsistencies

- **Overlap**: `cortex://rules/relevant/{task}` vs `cortex://synapse/rules/{task}` — two rules resources; clarify which is canonical.
- **Path style**: Most use hyphenated segments (load-context, suggest-refactoring); some use single words (stats, info, graph). Acceptable per rubric if consistent within domain.
- **context-effectiveness vs context-usage-statistics**: Long paths; consider shorter aliases if needed.

## 3. Prompts

**Source**: `.cortex/synapse/prompts/*.md`. Cursor commands map via `user-cortex/<slug>`.

| Filename | Expected slug | Command | Verb-first |
|----------|---------------|---------|------------|
| analyze.md | analyze | user-cortex/analyze | ✓ |
| commit.md | commit | user-cortex/commit | ✓ |
| create-plan.md | create-plan | user-cortex/create-plan | ✓ |
| fix-quality.md | fix-quality | user-cortex/fix-quality | ✓ (via fix_quality) |
| fix-tests.md | fix-tests | user-cortex/fix-tests | ✓ (via fix_tests) |
| docs-sync.md | docs-sync | user-cortex/docs-sync | ✓ |
| implement-next-roadmap-step.md | implement | user-cortex/implement | ✓ (slug shortened) |
| review.md | review | user-cortex/review | ✓ |
| REFACTORING_GUIDE.md | — | Not a command | — |
| REFACTORING_SUMMARY.md | — | Not a command | — |

### 3.1 Inconsistencies

- **Slug vs filename**: `implement-next-roadmap-step.md` maps to slug `implement` (shortened). Other prompts use filename-as-slug (e.g. create-plan, fix-quality).
- **Command name mapping**: Cursor command `user-cortex/fix_quality` uses snake_case; prompt file is `fix-quality.md`. Document mapping explicitly.

## 4. Summary of findings

| Area | Inconsistencies | Altitude gaps |
|------|-----------------|---------------|
| Tools | get_*vs query_*; noun dispatchers; sequentialthinking casing | Audit needed |
| Resources | rules vs synapse/rules overlap; path length variance | N/A (resources have no altitude rubric) |
| Prompts | implement slug vs filename; command slug casing | N/A |

## 5. References

- [Tool description altitude rubric](../guides/tool-description-altitude-rubric.md)
- [Tools vs Resources](../api/tools.md) — Phase 43 conventions
- [Tool optimization mapping](tool-optimization-mapping.md)
- [Tool optimization baseline](tool-optimization-baseline.md)
- Plan: [unify-simplify-tools-prompts-resources-naming](../../.cortex/plans/unify-simplify-tools-prompts-resources-naming.md)
