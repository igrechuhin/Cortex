---
title: "Spec-Driven Development Synapse Prompt"
component: synapse/prompts
work_type: feature
status: PENDING
priority: medium
created: 2026-04-02
depends_on: []
---

## Goal

Add a `/cortex/spec` Synapse prompt that implements the spec-driven development workflow from `spec-driven-development.md` in the ai-coding-kb. The prompt guides the agent through: brief → Markdown architecture document (with Mermaid diagrams) → review → phased implementation planning. The output is a richly structured plan file that can be handed off to `/cortex/do`.

## Context

The KB documents a proven pattern from TCS Bank: writing a full Markdown architecture doc before coding reduces cognitive load, surfaces design problems early, and produces better phased plans. Currently Cortex's `/cortex/plan` prompt jumps to implementation steps without requiring a design-doc phase. For new features (not bugfixes/refactors), a spec step would ensure the plan file contains: architecture diagram, component contracts, class/sequence diagrams, and per-phase readiness criteria. This pairs with the existing plan/do pipeline.

## Implementation Steps

### Step 1 — Draft `spec.md` Synapse prompt

- Create `.cortex/synapse/prompts/spec.md`
- Prompt structure:
  1. **Role**: Senior architect, output is a design document only (no code)
  2. **Phase A — Brief**: Extract feature name, requirements, constraints from user input
  3. **Phase B — Architecture doc**: Generate Markdown doc with:
     - `## Overview` (problem statement)
     - `## Architecture` + Mermaid component diagram
     - `## Data Model` + Mermaid class diagram (if relevant)
     - `## Sequence` + Mermaid sequence diagram for the happy path
     - `## Phase Plan` (3-5 phases, each ≤2h, must compile/pass tests)
     - `## Open Questions`
  4. **Phase C — Review gate**: Self-check that all referenced classes/functions are real; flag hallucinated APIs
  5. **Phase D — Plan file creation**: Call `plan(operation="create")` with the architecture doc as `content`, mark `work_type=spec`
  6. **Hard gate**: If Phase C finds hallucinated APIs, re-generate Phase B before creating plan
- Verification: File exists at `.cortex/synapse/prompts/spec.md`; prompt has all 4 phases.

### Step 2 — Register spec.md in prompts manifest

- Add `spec` entry to `.cortex/synapse/prompts/prompts-manifest.json`
- Fields: `name`, `description`, `file`, `tags: ["planning","architecture","spec"]`
- Verification: `prompts-manifest.json` contains `"spec"` entry; `plan list` shows it.

### Step 3 — Plan model: add `work_type=spec`

- Add `"spec"` to the `WorkType` enum / Literal in `src/cortex/tools/plans/plan_payloads.py`
- Verification: pyright passes; `plan(operation="create", work_type="spec")` does not raise.

### Step 4 — Roadmap display: spec plans shown separately

- In `update_memory_bank(operation="roadmap_add")`, if `work_type == "spec"` add to `### Spec & Architecture` section
- Verification: roadmap test confirms spec plans appear in correct section.

### Step 5 — `/cortex/plan` prompt: reference spec prompt

- Add note to `plan.md` Step 6: "For new features from scratch, consider running `/cortex/spec` first"
- Verification: `plan.md` contains `/cortex/spec` reference.

### Step 6 — Documentation

- Add `docs/guides/spec-driven-development.md` explaining when to use `/cortex/spec` vs `/cortex/plan`
- Include decision table: new feature (spec) / bugfix (plan) / refactor (plan) / prototype (plan)
- Verification: File exists with decision table.

## Verification Checklist

| Step | What to search for | Search scope | Files to re-read |
|------|-------------------|--------------|-----------------|
| 1 | `spec.md` file | `.cortex/synapse/prompts/` | spec.md |
| 1 | Phase A/B/C/D headers | spec.md | spec.md |
| 2 | `"spec"` entry | `prompts-manifest.json` | prompts-manifest.json |
| 3 | `spec` in WorkType | `src/cortex/tools/plans/plan_payloads.py` | plan_payloads.py |
| 4 | `Spec & Architecture` section | roadmap registration handler | register_helpers.py |
| 5 | `/cortex/spec` in plan.md | `.cortex/synapse/prompts/plan.md` | plan.md |
| 6 | `spec-driven-development.md` | `docs/guides/` | spec-driven-development.md |

## Dependencies

- `src/cortex/tools/plans/plan_payloads.py` — WorkType enum
- `.cortex/synapse/prompts/prompts-manifest.json` — prompt registration
- `.cortex/synapse/prompts/plan.md` — cross-reference update

## Success Criteria

- `spec.md` prompt produces architecture documents with Mermaid diagrams
- Phase C review gate catches hallucinated API references before plan is created
- `work_type=spec` is accepted by the plan tool without errors
- Plans of type spec appear in `### Spec & Architecture` roadmap section
- 95%+ coverage on new `work_type` code path
- Existing plan/do workflow is unaffected

## Testing Strategy

- Unit tests: `tests/unit/tools/plans/test_plan_payloads.py` — add `work_type="spec"` case
- Integration tests: `tests/integration/test_spec_prompt.py` — mock MCP call, verify spec plan file structure
- Snapshot tests: verify Mermaid diagram block is present in generated content
- 95%+ coverage on changed `plan_payloads.py` paths
