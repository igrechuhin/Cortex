# Session Optimization Improvements (2026-02-23)

Created from end-of-session analysis. Report: `.cortex/reviews/session-optimization-2026-02-23T11-56.md`.

## Recommendations

1. **Memory bank**: When appending completed work, consider checking for an existing same-title entry on the same date and either skip or merge to avoid duplicate bullets (e.g. "E2E Plan Test").
2. **Implement prompt**: For roadmap steps that reference a plan with all steps Done and no code changes, consider a short path: session_start → read plan → complete_plan (and optional load_context with small budget for rules only). Document in implement or session-start brief.
3. **Context effectiveness**: Ensure implement command always passes explicit `token_budget` (e.g. 10,000) for non-trivial steps; avoid relying on default or 0 so session logs and learned patterns stay accurate.
4. **Roadmap sync**: Extend or document `validate(roadmap_sync)` so that when `valid: false`, the response includes `missing_roadmap_entries`, `invalid_references`, or `unlinked_plans` to make fixes actionable.

## Status

COMPLETE (2026-02-23).
