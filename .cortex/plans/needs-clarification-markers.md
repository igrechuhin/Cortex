---
title: "NEEDS CLARIFICATION Markers in Plans"
component: planning
work_type: feature
status: IN_PROGRESS
priority: high
created: 2026-04-06
depends_on: []
---

## Goal

When `plan-creator` encounters ambiguity during plan generation, instead of asking the user immediately or silently guessing, embed `[NEEDS CLARIFICATION: <reason>]` markers inline in the plan document. The `review-completeness` agent surfaces all markers in one pass, and the user resolves them before implementation starts.

## Context

Inspired by GitHub Spec Kit's structured ambiguity markers. Currently, Cortex either blocks on clarifying questions (interrupting flow) or silently makes assumptions that get baked into implementation. Neither is ideal. Inline markers allow plan creation to complete, ambiguities to be batch-reviewed, and implementation to be gated until all markers are resolved.

## Implementation Steps

### Step 1: Define the marker format

- Standard format: `[NEEDS CLARIFICATION: <reason>]` — inline in any plan section.
- A marker can appear in: implementation steps, success criteria, testing strategy, or any prose section.
- Optional attribute: `[NEEDS CLARIFICATION(blocking): <reason>]` for markers that must be resolved before any implementation step can run.
- Add a `ClarificationMarker` Pydantic model in `src/cortex/core/models.py`: `reason: str`, `blocking: bool`, `location: str` (section + line ref), `resolved: bool`.

**Verification**: Model defined, format documented in a comment in `models.py`.

### Step 2: Add marker detection utility

- Add `find_clarification_markers(content: str) -> list[ClarificationMarker]` in `src/cortex/core/plan_utils.py` (new file or extend existing).
- Regex-based scan for `[NEEDS CLARIFICATION...]` pattern.
- Returns list of markers with `resolved=False`.

**Verification**: Function detects 0, 1, and multiple markers; correctly identifies `blocking` attribute.

### Step 3: Emit markers during plan creation

- In `plan(operation="create")`, when the plan-creator agent cannot determine a value:
  1. Insert a `[NEEDS CLARIFICATION: <reason>]` marker in place of the unknown value.
  2. Log how many markers were inserted.
  3. Include a `## Clarifications Needed` section at the top of the plan (after goal, before context) summarizing all markers and their locations.
- Do NOT block or ask the user during creation.

**Verification**: A plan created with ambiguous input contains markers and a summary section.

### Step 4: Gate `plan(operation="register")` on blocking markers

- Before registering a plan in the roadmap, call `find_clarification_markers()`.
- If any `blocking=True` markers exist, add the plan with status `BLOCKED` instead of `PENDING`, and include a note: "Blocked: N clarifications required before implementation."
- Non-blocking markers: register as `PENDING` with a note: "N clarifications pending (non-blocking)."

**Verification**: Plan with blocking markers registers as BLOCKED; plan with only non-blocking markers registers as PENDING.

### Step 5: Add marker resolution to `plan(operation="enrich")`

- Accept a `resolved_clarifications: dict[str, str]` parameter mapping `reason` → `resolution`.
- Replace resolved markers with the provided resolution text.
- Mark them `resolved=True` in the `## Clarifications Needed` section (or remove the section if all resolved).
- Append a delta entry (see delta-specs plan) for resolved markers.

**Verification**: Enriching with resolutions removes markers from the plan body; section disappears when all resolved.

### Step 6: Surface markers in `review-completeness` agent

- In the `review-completeness` agent prompt / tool, add a pass that scans the current plan for unresolved markers.
- Output: list of markers with location, blocking status, and suggested resolution approach.
- If any blocking markers remain, flag the plan as not ready for implementation.

**Verification**: `review-completeness` output includes marker list; blocking markers cause a NOT READY verdict.

### Step 7: Surface markers in `session()` startup

- In `session()`, scan all active plans for unresolved markers.
- Include a summary: "3 plans have unresolved clarifications (2 blocking)."

**Verification**: Session output includes marker summary when markers exist; no output when all resolved.

### Step 8: Tests

- Unit: `find_clarification_markers` — zero, one, many markers; blocking attribute detection.
- Unit: Plan creation with ambiguous content inserts markers.
- Unit: Registration status logic (BLOCKED vs PENDING based on blocking markers).
- Unit: Enrich with resolutions removes markers correctly.
- Integration: Full flow — create plan with markers → review → resolve → re-register.

**Verification**: All tests pass, ≥ 95% coverage on new code.

## Verification Checklist

| Step | What to search for | Search scope | Files to re-read |
|------|-------------------|--------------|-----------------|
| 1 | `ClarificationMarker` | `src/cortex/core/models.py` | full file |
| 2 | `find_clarification_markers` | `src/cortex/core/` | `plan_utils.py` |
| 3 | Marker insertion logic | `src/cortex/tools/plan.py` | `create` branch |
| 4 | BLOCKED registration | `src/cortex/tools/plan.py` | `register` branch |
| 5 | Marker resolution | `src/cortex/tools/plan.py` | `enrich` branch |
| 6 | Marker scan | `review-completeness` agent | prompt/tool |
| 7 | Marker summary | `src/cortex/tools/session.py` | startup logic |
| 8 | Test files | `tests/` | new test files |

## Dependencies

- Existing `plan` tool
- `review-completeness` agent
- `session()` tool
- `ClarificationMarker` model (Step 1)
- `find_clarification_markers` utility (Step 2)
- Delta specs feature (for Step 5 integration — can be implemented independently)

## Success Criteria

- Plans can be created with inline markers when ambiguity exists.
- Blocking markers cause BLOCKED roadmap status.
- `review-completeness` surfaces all unresolved markers.
- `session()` includes a marker summary.
- No `Any` types; functions ≤ 30 lines; ≥ 95% coverage.

## Testing Strategy

Target: 95% coverage on all new code paths.

- **Unit**: Marker detection (regex correctness, edge cases), registration logic, resolution logic.
- **Integration**: Full create → review → resolve → register cycle.
- **Edge cases**: Marker with no reason text; nested brackets in marker; marker inside code block (should not match); all markers resolved (section removed).

## Partial Progress Log

- 2026-04-06: Steps 1-2: ClarificationMarker model and find_clarification_markers() with unit tests — files: `src/cortex/core/models/_plan_markers.py`, `src/cortex/core/models/__init__.py`, `src/cortex/core/plan_utils.py`, `tests/unit/test_plan_utils_markers.py`
- 2026-04-06: Step 3: Added clarifications summary insertion in plan create flow and marker-count logging — files: `src/cortex/core/plan_utils.py`, `src/cortex/tools/plans/crud.py`, `tests/unit/test_plan_clarifications_summary.py`, `tests/integration/test_structured_plan_tools.py`
