---
title: "Agent Skills Specification Interoperability Assessment"
component: "docs"
work_type: docs
status: PENDING
priority: Low
created: 2026-08-06
depends_on: []
---

## Outcome

**NO-GO** (2026-08-06). Assessment written to
[Agent Skills specification interoperability assessment](../../../wiki/decisions/agent-skills-spec-interoperability-assessment.md).
No source, schema, or manifest was modified.

## Goal

Produce a written assessment comparing Cortex's `SkillPackManifest` format against the Agent Skills specification, ending in an explicit go or no-go recommendation on whether Cortex should consume or emit `SKILL.md`-format skills.

## Context

Cortex defines its own skill format: `SkillPackManifest` in `src/cortex/tools/skill_pack/models.py`, serialized as JSON under `src/cortex/resources/skills/`. A manifest carries `name`, `description`, `when_to_use`, `keywords`, `workflow_sequences`, `example_invocations`, `troubleshooting_tips`, and a `workflow` block of ordered `SkillWorkflowPhase` entries. Each phase names an MCP tool, an optional operation, and conditions, retries, inputs, and outputs. It is an executable directed workflow over MCP tool calls.

The Agent Skills specification, checked out locally at `~/Repo/skills/spec/agent-skills-spec.md` with a template at `~/Repo/skills/template/SKILL.md`, describes a different artifact: a directory containing a `SKILL.md` with YAML frontmatter of `name` and `description`, plus markdown instructions and optional bundled scripts and reference files. It is progressively disclosed context for a model to read, not a machine-executed workflow.

These are not the same kind of object. Cortex packs execute; Agent Skills instruct. A Cortex phase list has no `SKILL.md` equivalent, and a skill's bundled scripts and reference directories have no manifest equivalent. Any interoperability claim has to survive that mismatch, and it may not.

The honest reason this is a Low-priority assessment rather than an implementation plan is that the value is unproven. There is no current requirement to consume marketplace skills and no user asking to publish Cortex packs externally. What makes it worth an assessment at all is that the format decision is cheap to evaluate now and expensive to reverse later: if Cortex's manifest schema drifts further from a widely adopted standard, adopting that standard subsequently becomes a migration rather than an addition. The deliverable is therefore a decision, and "no, and here is why" is an entirely acceptable outcome that closes the question rather than leaving it open.

This plan writes a document. It changes no schema and no code.

## Scope

**in_scope**

- A field-by-field comparison of `SkillPackManifest` against the `SKILL.md` frontmatter and directory layout defined by the specification.
- Identification of concepts present in one format and absent from the other, in both directions.
- An assessment of whether Cortex packs could be emitted as valid Agent Skills, and at what fidelity loss.
- An assessment of whether marketplace `SKILL.md` skills could be consumed by Cortex, and what would execute them.
- An explicit go or no-go recommendation with stated reasoning, plus a rough effort estimate if the recommendation is go.
- The assessment document written to the wiki and linked from the roadmap.

**out_of_scope**

- Any change to `SkillPackManifest`, the manifests under `src/cortex/resources/skills/`, or the `skill_pack` tool.
- Implementing an importer, an exporter, or a converter in either direction.
- Adding a dependency on the `~/Repo/skills` repository or vendoring any part of it.
- Publishing Cortex packs to any marketplace.
- Skill-pack discovery and trigger accuracy, which is separate work.

## Approach

Read both specifications in full and build the comparison as a table before drawing any conclusion, so the recommendation follows from the mapping rather than from a prior intuition about it. Work in both directions explicitly, because the two are not symmetric: emitting a Cortex pack as a `SKILL.md` mostly discards the executable workflow, while consuming a `SKILL.md` as a Cortex pack requires inventing a workflow that does not exist in the source.

Treat the executable-versus-instructional distinction as the central question rather than a detail. If the `workflow` block has no representation in the target format, then export is lossy in the one dimension that makes a Cortex pack useful, and that fact alone may settle the recommendation.

State the recommendation plainly, with its reasoning, and include the effort estimate only if the recommendation is go. A no-go must record what would have to change for the answer to become yes, so the question can be reopened on evidence rather than re-litigated from scratch.

## Implementation Steps

1. Read `~/Repo/skills/spec/agent-skills-spec.md` in full and record the required and optional fields, the directory layout, and the progressive-disclosure loading model.
2. Read `~/Repo/skills/template/SKILL.md` and two contrasting real examples from `~/Repo/skills/skills/` — one simple and one with bundled scripts and reference files.
3. Re-read `src/cortex/tools/skill_pack/models.py` and record every field of `SkillPackManifest`, `SkillWorkflow`, and `SkillWorkflowPhase`.
4. Build the field-by-field mapping table, marking each field as directly mappable, lossy, or unrepresentable in the other format.
5. Assess the export direction: what a Cortex pack becomes as a `SKILL.md`, and specifically what happens to the `workflow` phase list, its conditions, retries, and input and output wiring.
6. Assess the import direction: what a marketplace `SKILL.md` becomes as a Cortex pack, and identify what component would execute a skill that carries instructions but no phase list.
7. Write the go or no-go recommendation with explicit reasoning; if go, give a rough effort estimate and name the smallest useful first slice; if no-go, record the conditions under which the question should be revisited.
8. Write the assessment to `.cortex/wiki/` using `manage_file()`, and record the Agent Skills specification source and its license.
9. Run `run_docs_gate()` and resolve every finding.

## Verification Checklist

- Step 1: confirm the specification version or commit is recorded, so the assessment can be re-checked against a later revision.
- Step 3: cross-check the recorded field list against `models.py` directly; confirm no field of the three models is missing from the table.
- Step 4: confirm every field appears in the table exactly once and carries a mappability verdict.
- Steps 5 and 6: confirm both directions are assessed and that neither section concludes without naming its fidelity loss.
- Step 7: confirm the document contains an unambiguous "go" or "no-go" string and its reasoning, not a hedge.
- Step 8: read the written page back and confirm all links resolve.
- Step 9: re-read every file the docs gate modified.

## Dependencies

- None on other Cortex plans.
- Reference sources: `~/Repo/skills/spec/agent-skills-spec.md`, `~/Repo/skills/template/SKILL.md`, and example skills in that checkout.

## Success Criteria

- A wiki page exists containing the complete field-by-field mapping table, with every `SkillPackManifest`, `SkillWorkflow`, and `SkillWorkflowPhase` field classified as mappable, lossy, or unrepresentable.
- Both the export and import directions are assessed, each naming its specific fidelity loss.
- The document states an explicit go or no-go recommendation with reasoning.
- A no-go records the conditions for revisiting; a go records an effort estimate and the smallest useful first slice.
- The specification version or commit is recorded.
- No source file, schema, or manifest is modified by this plan.
- `run_docs_gate()` reports zero errors.

## Testing Strategy

This plan produces a document, not code, so there is no unit-test surface and the 95% coverage target does not apply. Verification is by review against the checklist above, plus the automated documentation checks.

- Automated — `run_docs_gate()` must pass, covering markdown lint, link validity, and memory-bank consistency.
- Automated — link validation confirms every reference to a repository path or wiki page resolves.
- Manual — completeness review: every model field appears in the mapping table exactly once, verified against `models.py`.
- Manual — decision review: the recommendation is unambiguous and its reasoning follows from the table rather than asserting a conclusion the mapping does not support.
- Regression — confirm `git status` shows no modification under `src/` or `src/cortex/resources/skills/`, enforcing the no-code-change boundary.

## Risks and Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Assessment concludes no-go, making the effort look wasted | Perceived low value | A recorded no-go with revisit conditions is a real deliverable; it closes an open question cheaply and prevents repeated re-litigation |
| Scope creeps from assessment into implementing a converter | Unplanned schema and code churn | Explicit out-of-scope entries plus a regression check that no file under `src/` changed |
| The external specification changes after the assessment | Conclusions silently go stale | Record the specification version or commit; revisit conditions name spec revision as a trigger |
| The comparison is drawn toward a predetermined answer | Recommendation not supported by evidence | Mapping table is built and reviewed before the recommendation is written; decision review checks the conclusion follows from the table |
| Local `~/Repo/skills` checkout is unavailable to a later executor | Plan cannot be executed as written | Step 1 records the specification content and version into the assessment itself, so the document stands alone |
