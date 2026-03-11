---
title: "Calibrate Review Metric Scores with Examples"
component: "synapse/prompts/review"
work_type: "fix"
status: "IN_PROGRESS"
priority: "Medium"
created: "2026-03-07"
execution_order: 15
depends_on: []
---

# Calibrate Review Metric Scores with Examples

**Status**: IN_PROGRESS
**Priority**: Medium
**Complexity**: Low
**Category**: Fix
**Component**: synapse/prompts/review
**Work Type**: fix
**Execution Order**: 15

## Goal

Add calibration examples for each of the 9 review metrics to prevent score inflation (LLMs default to 6-8) and require tool-based evidence for each score.

## Context

- `review.md` defines 9 mandatory metrics scored 0-10: Architecture, Test Coverage, Documentation, Code Style, Error Handling, Performance, Security, Maintainability, Rules Compliance.
- No calibration examples exist. LLMs tend toward middle scores without differentiating.
- Review scores should be evidence-based (tool output cited) not subjective impressions.

## Implementation Steps

> PARTIAL (2026-03-11): Step 3 completed — `review-output-schema.md` now exposes a `metrics` structure with `score` and `evidence` fields for all 9 review metrics. Steps 1–2 (calibration tables and evidence instructions in `review.md`) were already present before this session; a future quality gate run should verify end-to-end behavior.

### Step 1: Add calibration table to review.md

**File**: `.cortex/synapse/prompts/review.md` (after the metrics list, around line 141)

Add for each metric a calibration table. Example for Test Coverage:

```markdown
#### Test Coverage Calibration
| Score | Meaning | Evidence Required |
|---|---|---|
| 0-2 | No tests or < 30% coverage | `pytest --cov` output showing < 30% |
| 3-4 | Happy path only, 30-60% | Coverage report showing gaps |
| 5-6 | Good coverage 60-80%, some edge cases | Coverage report |
| 7-8 | Strong coverage 80-95%, edge cases covered | Coverage report + edge case test names |
| 9-10 | Exhaustive 95%+, mutation testing or property tests | Coverage report + mutation/property test evidence |
```

Similar tables for all 9 metrics.

### Step 2: Add evidence requirement to scoring instructions

**File**: `.cortex/synapse/prompts/review.md`

Add GATE instruction: "Each metric score MUST cite specific tool output or code evidence. Scores without evidence are invalid. Example: 'Test Coverage: 7 — pytest shows 85% coverage, edge cases in test_parser_edge_cases.py.'"

### Step 3: Update review-output-schema.md

**File**: `.cortex/synapse/agents/review-output-schema.md`

Add `evidence: str` field to each metric in the output schema.

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `Calibration` | `review.md` | 9 calibration tables present |
| `evidence` | `review-output-schema.md` | Evidence field per metric |

## Dependencies

- None.

## Success Criteria

- All 9 metrics have calibration examples with score ranges.
- Evidence is required for every score.
- Output schema includes evidence field.

## Testing Strategy

- **Coverage Target**: N/A (Synapse prompt changes)
- **Manual verification**: Run a review and verify scores include evidence citations.
