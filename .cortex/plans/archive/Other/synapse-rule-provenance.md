---
title: "Synapse Rule Provenance from Experience Pairs"
component: "synapse"
work_type: "feature"
status: PENDING
priority: "Medium"
created: "2026-07-19"
depends_on: ["unified-experience-store", "analyze-experience-graph-queries"]
---

## Goal

Give Synapse rule recommendations provenance: each recommended or existing rule carries citations to the experience-store node pairs (failure → fix) that justify it, and rules whose cited failure patterns stop occurring are flagged as pruning candidates.

## Context

Synapse already distills experience across projects into rules and prompts, but distillation has no provenance — nothing records which concrete failures a rule prevents, so stale rules accumulate and recommendations are hard to audit. The Experience Graphs paper (arXiv:2606.29823) closes the self-improving loop by keeping evidence queryable; applied at dev-tool scale, each rule can cite the node pairs that justify it (produced by plan `analyze-experience-graph-queries`), and a periodic check can flag rules that no longer match real failures. This strengthens the Compound step of the Plan→Work→Review→Compound loop.

## Scope

**in_scope**

- Provenance model: rule id ↔ evidence links (node-pair ids, project, date) stored alongside the experience store (not inside the Synapse submodule's rule files' normative content).
- Analyze-pipeline emission: rule recommendations include evidence citations; accepted rules persist their links.
- Staleness report: rules whose cited failure class has zero new occurrences within a configurable window are listed as pruning candidates in analyze output.
- Read API for "why does this rule exist" (rule id → evidence pairs with artifact refs).

**out_of_scope**

- Automatic rule deletion — pruning stays a human decision surfaced in reports.
- Rewriting existing Synapse rules retroactively; provenance accrues from feature enablement.
- Cross-project federation of experience stores (single-project provenance only).
- The pair-extraction queries themselves (plan: analyze-experience-graph-queries).

## Approach

Add a `rule_provenance` table linking Synapse rule identifiers to evidence node pairs, populated when the analyze pipeline emits or updates a rule recommendation. Extend the analyze report with a provenance section and a staleness pass that counts recent occurrences of each rule's cited failure class. Expose a small typed query API so `rules()`-related tooling can display justification on demand.

## Implementation Steps

1. Define `RuleProvenance` Pydantic model and SQLite table (rule_id, pair_ids, created, last_matched, failure_class).
2. Populate provenance when analyze emits rule recommendations (extend the emission path from plan analyze-experience-graph-queries).
3. Implement `last_matched` refresh: when new preference pairs match a rule's failure class, update the link.
4. Implement staleness query: rules with no matches within the window → pruning-candidate list.
5. Add provenance and pruning sections to the analyze report output.
6. Add read API `rule_evidence(rule_id)` returning cited pairs with artifact references.
7. Tests over fixture stores and fixture rule sets.
8. Document the provenance lifecycle in memory bank and Synapse docs.

## Verification Checklist

- Step 2: trace the recommendation emission path (`rg "recommendation" src/` in analyze modules) and confirm every emitted rule writes provenance; re-read emission module after edits.
- Step 4: verify window logic against fixture timestamps (no reliance on wall-clock in tests).
- Step 5: confirm analyze report schema consumers handle new sections (`rg "analyze" tests/`).
- Step 7: `run_quality_gate()` green.

## Dependencies

- Plan: `unified-experience-store` (`.cortex/plans/unified-experience-store.md`).
- Plan: `analyze-experience-graph-queries` (`.cortex/plans/analyze-experience-graph-queries.md`) — produces the evidence pairs.

## Success Criteria

- Every rule recommendation emitted by analyze after this plan carries ≥1 evidence citation resolvable to stored node pairs.
- `rule_evidence(rule_id)` returns the exact pairs cited at emission time.
- A fixture rule whose failure class has no occurrences within the window appears in the pruning-candidate list; one with recent matches does not.
- No modification to Synapse rule file normative content is required for provenance to function.
- Quality gate green; ≥95% coverage on new modules.

## Testing Strategy

- Unit tests (AAA): provenance model, last_matched refresh, staleness window edge cases (boundary dates, empty history).
- Integration tests: analyze run on fixture store emits cited recommendations; pruning report generation; evidence read API round-trip.
- Negative cases: dangling pair ids, unknown rule ids, empty provenance table.
- Target: ≥95% coverage on new modules.

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Failure-class matching is too coarse/fine, mislabeling staleness | Start with analyzer's existing pattern taxonomy; make window and class mapping configurable |
| Provenance data diverges from Synapse submodule rule ids | Store rule ids by stable file/slug; validation pass flags unresolved ids |
| Pruning list encourages deleting still-valuable rare-failure rules | Human-in-the-loop only; report shows last-matched date, never auto-deletes |
| Coupling analyze report schema to provenance internals | Typed report models; additive schema versioning |

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
