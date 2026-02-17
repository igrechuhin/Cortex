# Session Optimization: Path Resolver and Context Loading (2026-02-11)

## Source

End-of-session analysis report: `session-optimization-2026-02-11T22-48.md` (reviews directory).

## Recommendations Summary

1. **Path resolution in tests and rules** – Document in Synapse or project rules that tests (and agents) must resolve `.cortex` or Synapse paths via `path_resolver` (`get_cortex_path`, `get_structure_info`) and must not hardcode `.cortex/` or `.cursor/` paths. Reference the pattern in `test_check_async_tests_script.py` and AGENTS.md/CLAUDE.md.

2. **Context loading for session/commit-pipeline tasks** – For task descriptions that mention "Session Optimization", "Commit Pipeline", or "roadmap step", consider including `roadmap.md` and `activeContext.md` in the selected set when token budget allows (e.g. 10k), so next steps and completed work are both in context.

3. **Continue existing plan** – Session Optimization: Commit Pipeline Improvements (steps 2–6, 9) remains in the roadmap; execute when picking the next PENDING step. No new plan required for this item.

## Plan Steps

1. **Rule: path_resolver for .cortex/synapse paths** – Add or update a Synapse rule (or project coding standard): require use of `path_resolver` (`get_cortex_path`, `get_structure_info`) for any `.cortex` or Synapse paths in tests and procedures; prohibit hardcoded `.cortex/` or `.cursor/` paths. Reference `test_check_async_tests_script.py` and AGENTS.md/CLAUDE.md.
2. **Implement/load_context: include roadmap and activeContext for session/commit tasks** – Update implement-next-roadmap-step or load_context strategy so that for task descriptions containing "Session Optimization", "Commit Pipeline", or "roadmap step", the recommended or default set includes `roadmap.md` and `activeContext.md` when budget allows (e.g. 10k).
3. **No new plan for Commit Pipeline Improvements** – Continue tracking via existing roadmap entry; execute remaining steps (2–6, 9) when selecting next PENDING item.

## Status

COMPLETE

## Completion Criteria

- Rule or doc updated for path_resolver in tests; no new hardcoded .cortex paths in tests.
- Implement or load_context guidance updated for session/commit-pipeline task types.
- Existing Commit Pipeline Improvements plan advanced as per roadmap order.
