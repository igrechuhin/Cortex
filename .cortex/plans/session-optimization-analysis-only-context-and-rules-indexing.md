# Session Optimization: Analysis-Only Context and Rules Indexing

## Source

Created from end-of-session analysis report: `.cortex/reviews/session-optimization-2026-02-16T21-00.md`.

## Objective

Address three improvement areas identified in the 2026-02-16 analysis: (1) context effectiveness when sessions are analysis-only, (2) rules indexing returning zero rules, (3) optional verification of memory bank read behavior.

## Recommendations from Analysis

### 1. Context effectiveness in analysis-only sessions

When the only action in a session is running `/cortex/analyze`, current-session context effectiveness will be "no_data" because no `load_context` was called.

- **Action**: Document in the Analyze prompt or troubleshooting that this is expected.
- **Optional**: Suggest in the Analyze prompt that agents may call `session_start()` or `load_context(task_description="end-of-session analysis")` before running analysis so one call is recorded for context-effectiveness metrics.

### 2. Rules indexing for get_relevant

`rules(operation="get_relevant", task_description="...")` returned 0 rules (indexed_files: 0).

- **Action**: If analysis or other flows depend on project rules, ensure the rules directory is populated and indexing has run.
- **Action**: Document fallback to Synapse / AGENTS.md when rules index is empty (e.g. in troubleshooting or in the rules tool description).

### 3. Memory bank read content

`manage_file(operation="read")` for activeContext, roadmap, systemPatterns, techContext, progress returned empty content in the analysis run.

- **Action**: If this is due to section filtering or genuinely empty files, no change needed.
- **Action**: If it indicates a bug, verify `manage_file` read behavior for full-file reads (no sections filter) and fix if needed.

## Success Criteria

- Analyze prompt or troubleshooting updated to describe analysis-only "no_data" behavior and optional load_context/session_start.
- Rules indexing behavior and fallback documented where relevant.
- Any confirmed bug in manage_file full-file read fixed; otherwise close as expected behavior.

## Status

PENDING.
