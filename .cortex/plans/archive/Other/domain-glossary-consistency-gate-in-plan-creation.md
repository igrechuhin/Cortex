---
title: "Domain Glossary Consistency Gate in Plan Creation"
component: "synapse-prompts"
work_type: feature
status: PENDING
priority: Medium
created: 2026-08-02
depends_on: []
---

## Goal

Give Cortex a canonical domain glossary and have `plan-creator` check every new plan's terminology against it, flagging terms that collide with, duplicate, or contradict established project vocabulary before the plan is registered.

## Context

The aihero.dev skills pack's `/domain-model` skill enforces what it calls "the glossary-and-ADR discipline": a `CONTEXT.md` glossary plus architecture decision records, with new plans checked against the codebase's existing domain language before they proceed.

Cortex has adjacent machinery — a 108-page `.cortex/wiki` and a memory bank — but nothing enforces terminology consistency at plan time. The practical failure mode is visible in this repository already: overlapping vocabulary such as prompt / skill / command / agent / subagent, and plan / roadmap entry / step / task, is used inconsistently across prompts and plans. Each new plan is free to coin a synonym for an existing concept, and nothing catches it. Over time this degrades both the wiki's usefulness and the agent's ability to resolve a reference to the right artifact.

The check is cheap and belongs exactly where plans are created, because that is the point where new vocabulary enters the system.

## Scope

**in_scope**

- A canonical glossary file (`.cortex/wiki/glossary.md`) with a defined entry schema: term, definition, aliases, "not to be confused with"
- Seeding the glossary from the existing vocabulary in prompts, plans, and the wiki
- A glossary lookup surfaced through the existing `cortex://` resource or wiki read path
- A terminology check in `plan-creator` (Step 7 of `plan.md`) that runs before roadmap registration
- Advisory-not-blocking behavior on first release: report collisions to the user, do not fail plan creation
- Tests for the glossary parser and collision detection

**out_of_scope**

- Architecture decision records — a distinct artifact, deferred to a follow-up
- Retroactive terminology cleanup of existing plans, prompts, or wiki pages
- Enforcing the glossary in `do.md`, `review.md`, or code review
- Automatic glossary population from source code identifiers
- Making the gate blocking; escalation from advisory to blocking is a follow-up decision informed by observed false-positive rate

## Approach

Start with the artifact, not the enforcement. Seed `.cortex/wiki/glossary.md` by extracting the domain nouns already in circulation across `.cortex/synapse/prompts/`, `.cortex/plans/`, and the memory bank, then curate that list down to terms that genuinely carry project-specific meaning. A glossary that mixes real domain terms with generic English is worse than none, because every check becomes noise.

Detection is deliberately conservative. Flag three cases: a plan uses a term that is a declared alias of a canonical term (suggest the canonical form); a plan introduces a term that is a near-match of an existing canonical term but not declared as an alias (possible unintended synonym); a plan uses a term listed in another term's "not to be confused with" field in a context suggesting confusion. Anything subtler is out of reach for a lexical check and should not be attempted.

Ship advisory-only. The value on day one is visibility, and a blocking gate with an untuned false-positive rate would train users to bypass it. Collect observed hit quality first, then decide about escalation.

## Implementation Steps

1. Extract candidate domain terms from `.cortex/synapse/prompts/*.md`, `.cortex/plans/*.md`, and `.cortex/memory-bank/*.md`; write the raw candidate list to a scratch report.
2. Curate the candidates into canonical terms, discarding generic English and keeping only project-specific vocabulary.
3. Define the glossary entry schema and write `.cortex/wiki/glossary.md` with the curated terms, populating aliases and "not to be confused with" for the known overlaps (prompt/skill/command/agent/subagent, plan/roadmap entry/step/task).
4. Implement a glossary parser returning a Pydantic model of entries; no untyped dict access.
5. Implement collision detection covering exactly the three flagged cases; return typed findings with term, matched canonical term, case, and suggested replacement.
6. Surface the glossary through the existing wiki read path so `plan-creator` can load it without a new tool.
7. Wire the check into `plan.md` Step 7, after the plan body is written and before Step 8 registration; report findings in the narrative, do not block.
8. Extend the `/cortex/plan` final report with a Terminology row listing findings, or "No collisions".
9. Write tests for the parser, each detection case, and the advisory (non-blocking) behavior.
10. Run `run_quality_gate()` and `run_docs_gate()` until clean.

## Verification Checklist

- Step 2-3: re-read `glossary.md`; confirm every entry has all four schema fields and that no generic-English term survived curation.
- Step 4: grep the parser for `dict[str, Any]` and `Any`; confirm zero occurrences.
- Step 5: confirm exactly the three specified cases are implemented and no heuristic beyond them was added.
- Step 6: confirm no new MCP tool was introduced; the glossary loads through the existing wiki path.
- Step 7: re-read `plan.md` Step 7; confirm the check is stated as advisory and cannot abort registration.
- Step 8: confirm the final-report template still matches the Artifact format required by `plan.md`.
- After all steps: run `/cortex/plan` on a throwaway topic using a known alias; confirm the collision is reported and the plan is still created.

## Dependencies

None hard. Independent of the `shape.md` and shared-prompt-layer plans. If `shape.md` lands first, the shaping record is a natural additional input to the terminology check, but this plan does not require it.

## Success Criteria

- `.cortex/wiki/glossary.md` exists with curated entries, each carrying term, definition, aliases, and "not to be confused with"
- The known overlapping vocabulary sets (prompt/skill/command/agent/subagent, plan/roadmap entry/step/task) are disambiguated in the glossary
- `plan-creator` reports terminology collisions for all three detection cases
- Plan creation succeeds even when collisions are found — the gate is advisory
- The `/cortex/plan` final report includes a Terminology row
- No new MCP tool was added and no `Any` type was introduced
- `run_quality_gate()` and `run_docs_gate()` both pass
- New code paths reach the 95% coverage target

## Testing Strategy

Target 95% coverage on changed lines, AAA pattern, `tests/wiki/test_glossary_gate.py`.

- Unit — parser positive: well-formed glossary parses to typed entries; entries with empty alias lists handled; multiple aliases per term handled.
- Unit — parser negative: malformed entry, missing required field, duplicate canonical term, empty glossary file.
- Unit — detection, one test per case: declared-alias hit; near-match undeclared synonym; "not to be confused with" hit. Plus a clean plan producing zero findings.
- Unit — false-positive guard: a plan using a canonical term correctly must not be flagged.
- Integration: `plan(operation="create")` with a colliding plan body — assert findings are returned *and* the plan file is written and registerable.
- Docs: markdown lint over `glossary.md`.

## Risks and Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| High false-positive rate trains users to ignore the gate | Feature becomes noise and is bypassed | Advisory-only on release; detection restricted to three conservative cases; false-positive guard test |
| Glossary polluted with generic English | Every check fires; signal destroyed | Explicit curation step separate from extraction; verification checklist re-reads the file for generic terms |
| Glossary goes stale as vocabulary evolves | Gate enforces obsolete terminology | Glossary lives in the wiki and is updatable via the normal memory-bank flow; staleness surfaces as false positives that prompt an update |
| Near-match detection is too fuzzy or too strict | Misses real synonyms or floods findings | Threshold chosen against the seeded glossary and pinned by tests; case is reported as "possible", not asserted |
| Check slows plan creation noticeably | Friction on the most-used prompt | Lexical check over a curated list is small; glossary loads through the existing cached wiki read path |

## Change History

*No revisions recorded yet — enrich or edit implementation steps to append history.*
