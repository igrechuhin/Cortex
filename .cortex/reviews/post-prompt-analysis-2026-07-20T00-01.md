# Post-Prompt Analysis — /cortex/do (2026-07-20T00-01)

## Summary

Post-prompt hook run after the implement pipeline completed "Unified Experience Store in SQLite" (plan archived, gates green). One actionable finding routed to a new plan; no skill or rule artifacts warranted.

## Context Effectiveness

- Session `fb7d5600d0e0`: 18 calls analyzed; avg token utilization 0.348; avg relevance 0.363.
- One telemetry anomaly: a zero-budget call recorded relevance scores without selected files (`record_quality: invalid_data`, note `relevance_scores_without_selected_files`).
- Global insights: average 41% budget utilization (~17k tokens unused per call); `projectBrief.md` loaded in 346/347 calls with 0.482 avg relevance ("consider excluding for most tasks").

## Session Optimization

- `usage_patterns` analysis returned empty patterns (no access-frequency/co-access/task-pattern data in the 30-day window) — no mistake patterns derived.
- Session scope: single-goal (implement unified-experience-store); one in-scope docs-gate detour (roadmap_sync false positive). No multi-goal scope risk.
- Token budget: `log.md` (8645 words), `progress.md` (4190), `techContext.md` (1770), `activeContext.md` (1297), `systemPatterns.md` (1189) are compression candidates; `compress_memory_bank()` suggested.

## Tools Optimization

- Tool budget: 13 registered tools vs target 40 — well under budget; no dead tools, duplicates, or consolidation candidates.
- One optimization note: `manage_file` docstring is very long (7257 chars); consider splitting documentation.

## Finding Routed to Plan

- roadmap_sync false positive: the file-reference regex in `src/cortex/validation/roadmap_sync.py` lacks the `json` extension, truncating `failure_based_evals.json` to a phantom `failure_based_evals.js` and failing the docs gate. Session workaround: reworded the roadmap entry. Durable fix tracked in `.cortex/plans/fix-roadmap-sync-json-extension.md` (registered in roadmap pending section).

## Compaction

Compaction skipped (not required for this prompt).

## Post-Prompt Hook Result

| Artifact Type | Produced | Location or Notes |
|---------------|----------|-------------------|
| Skill         | No       | No recurring tool-sequence pattern observed |
| Plan          | Yes      | .cortex/plans/fix-roadmap-sync-json-extension.md |
| Rule          | No       | No recurring rule violations in session |

Report saved: `.cortex/reviews/post-prompt-analysis-2026-07-20T00-01.md`
