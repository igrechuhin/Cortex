---
title: "Revision-bound plan-scoped context packets"
component: context-assembly
work_type: feature
status: DONE
priority: High
created: 2026-10-21
depends_on: []
execution: agent
---

## Goal

Make the existing plan-scoped context packet revision-bound and visibly fresh or conflicting for its selected task sources.

## Context

src/cortex/tools/context/scoped_context.py already assembles selected plans, completed dependencies and filtered rules. core/session_goal_models.py already holds goal and allowed/blocked paths; optimization/context_appenders.py already supplies memory/wiki/artifact/decision provenance. optimization/handlers.py:403-414 caches task/budget/scope/layers/topic/query without source-byte revisions. No explicit revision manifest or structured freshness/conflict result exists in the scoped packet. Source: <https://www.anthropic.com/research/effective-context-engineering-for-ai-agents> . Cortex adaptation only.

## Scope

**in_scope**

- A typed revision/provenance manifest for only selected existing plan, dependency, goal/prohibition, decision-summary and rule/context inputs.
- Compact goal, status, dependency readiness, prohibitions and open-decision summary using existing sources; details remain on demand.
- Revision-aware cache validation plus explicit stale/conflict warnings for inconsistent selected inputs.

**out_of_scope**

- New memory store, replacement wiki, global context framework or duplicate decision journal.
- Silently resolving conflicting instructions, loading full history by default, or inventing unspecified decisions.

## Approach

Extend existing scoped assembly and cache ownership rather than building another context system. Keep source identity/digest/provenance alongside compact task state, and revalidate selected revisions before cache reuse. Reuse existing memory/wiki and exploration summaries for decisions, explicitly marking missing evidence.

Keep no commits/pushes/dependencies/permission changes/shared restarts in this planning task. Future implementation uses the normal supported Cortex flow and `# AI:` comments only for non-obvious invariants.

## Implementation Steps

1. Map source selection in scoped_context, session_goal_builder and context_appenders; define a bounded typed revision manifest and precedence/conflict contract.
2. Assemble compact current task state and source provenance over those existing inputs, with references for on-demand details.
3. Include selected revisions in cache validity and reject or warn on inconsistent snapshots without silently combining stale and fresh state.
4. Add deterministic same-task source-mutation, dependency-change, prohibition-change, conflicting-input and cache-reuse cases; update API docs.

## Verification Checklist

- [ ] Re-read src/cortex/tools/context/scoped_context.py, src/cortex/tools/optimization/handlers.py and context_appenders.py, src/cortex/core/session_goal_models.py and session_goal_builder.py.
- [ ] Confirm existing L0-L3 layers, wiki/memory ownership and source-selection rules remain the only stores.
- [ ] Verify unrelated source edits do not expand packet scope, and relevant edits invalidate reuse before a stale response is served.

## Dependencies

The registration repair is not an implementation prerequisite. Preserve any other dependencies declared in frontmatter. The user explicitly authorized implementation through the existing sequential Cortex do loop; the earlier planning-only hold is superseded. Preserve the declared dependency graph and all safety constraints. Reuse the completed mechanisms named in Context; do not reactivate archived plans.

## Success Criteria

- Each selected source has stable identity, exact revision and provenance in the existing scoped packet.
- Relevant edits with the same task/cache key produce fresh task state, not a stale cached packet.
- Goal/status/deps/prohibitions/open decisions are compact, evidence-linked and missing/conflicting inputs are explicit.
- Detail-on-demand and current context budget behavior remain intact with no new memory store.

## Testing Strategy

AAA fixtures with exact source revisions; test relevant versus unrelated mutations, cache hit/miss, missing/conflicting metadata, dependency readiness and budget boundaries. Target 95% changed-code coverage plus a real scoped-context read/mutate/read smoke.

## Risks and Mitigation

| Risk | Mitigation |
| --- | --- |
| Digest work expands to entire repository | Hash only sources selected by the existing builder. |
| Warnings become invented authority | Report conflicts and provenance; do not override operator decisions. |
| New packet duplicates existing memory | Add fields to existing packet and reuse canonical stores. |

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
