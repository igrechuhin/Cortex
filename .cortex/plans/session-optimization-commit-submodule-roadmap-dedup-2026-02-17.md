# Session Optimization: Commit Submodule and Roadmap Deduplication (2026-02-17 Analysis)

**Status**: PENDING
**Source**: End-of-session analysis 2026-02-17 (session-optimization-2026-02-17T11-29.md)

## Goal

Improve commit pipeline and roadmap behavior based on 2026-02-17 session: submodule push handling, roadmap duplicate blockers, plan status alignment with activeContext.

## Recommendations (from analysis)

1. **Commit prompt / Step 11**: Document that after submodule commit, if push fails (e.g. auth), user can proceed with parent commit and push submodule manually later; link to troubleshooting and git-operations.
2. **Roadmap / MCP tool failure flow**: When adding blocker entries for the same plan (same plan file path), deduplicate or provide bulk-remove by plan path to avoid many duplicate bullets.
3. **Plan archiver / implement Step 5**: When marking a plan complete in activeContext, update plan file Status to COMPLETE so archiver detects it; or document archiving by plan path + date when activeContext shows COMPLETE.

## Implementation Steps

1. Update commit prompt Step 11 (or Connection Closed / Submodule section) with one-line note: submodule push failure non-blocking for parent; push submodule manually; link docs.
2. Review MCP tool failure handler / roadmap add logic: add deduplication check (existing bullet with same plan path) or add_roadmap_entry option to replace/skip duplicate.
3. Document in plan-archiver or memory-bank-updater: when completing an investigation, set plan Status to COMPLETE before or during archive so detection is consistent.

## Success Criteria

- Commit prompt clearly states submodule push can be retried manually.
- Roadmap no longer accumulates duplicate blocker entries for the same plan.
- Completed investigations are archived with Status COMPLETE in plan file or documented exception.

## Notes

Analysis report: `.cortex/reviews/session-optimization-2026-02-17T11-29.md`
