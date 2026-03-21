---
title: "Fix review prompt to track issues across reviews and stop score plateau"
component: synapse
work_type: fix
status: PENDING
priority: high
created: 2026-03-21
depends_on: []
---

## Goal

Restructure the review prompt so that reviews track issues across sessions, scope to meaningful code (not just telemetry diffs), and produce concrete actionable findings — breaking the 7.2-7.9 score plateau observed across 14 consecutive reviews.

## Context

Analysis of 14 reviews in `.cortex/reviews/` reveals three structural problems:

1. **Reviews scope to `git diff`, not previous findings**: Most commits only change `.cortex/.session/` telemetry. The review falls back to "representative `src/` inspection" — a shallow grep for `except Exception` every time. It never targets files/issues from the previous review.

2. **No issue tracking between reviews**: Each review starts fresh. It "discovers" the same `except Exception` pattern, scores it the same, suggests the same "narrow exception handlers" improvement — across all 14 reviews.

3. **Improvement suggestions are unspecific**: Every review suggests "narrow exception handlers (Effort: Medium, Impact: Medium)" without concrete file:line, before/after code, or single-commit scope. Plans from these suggestions are equally vague.

Evidence:

- Scores: 7.3, 7.9, 7.4, 7.2, 7.7, 6.6, 7.6, 6.7, 8.7, 7.4, 7.4, 7.6, 7.9 (mean: 7.4, stdev: 0.5)
- "except Exception" flagged in 12 of 14 reviews
- Same `pipeline_handoff` path sanitization finding appears in 4 reviews
- Zero issues marked as "resolved since last review"

## Implementation Steps

### Step 1: Add issue-tracking section to review report format

- **File**: `.cortex/synapse/prompts/review.md` (Report Format section)
- Add required section: "## Issue Tracker" with columns: ID | First Found | Status | Location | Description
- Issue ID format: `REV-{YYYY-MM-DD}-{N}` (e.g. `REV-2026-03-21-1`)
- Status values: `OPEN`, `RESOLVED`, `WONTFIX`
- Require: before scoring, load the most recent `.cortex/reviews/code-review-report-*.md` and carry forward all OPEN issues, marking resolved ones

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| "Issue Tracker" section in prompt | `.cortex/synapse/prompts/review.md` | review.md |
| Issue ID format guidance | review.md | review.md |

### Step 2: Change scoping rules for telemetry-only diffs

- **File**: `.cortex/synapse/prompts/review.md` (Step 2 scope)
- Add rule: "If `git diff --name-only` only shows `.cortex/.session/`, `.cortex/synapse/.cache/`, or other telemetry/metadata files — expand scope to: (a) all OPEN issues from the previous review, (b) files modified in the last 5 commits (`git log --oneline -5 --name-only`)"
- This ensures reviews always target meaningful code, not just JSON counters

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| Telemetry-only scope fallback | review.md | review.md Step 2 |
| "previous review" loading logic | review.md | review.md |

### Step 3: Require concrete before/after in improvement suggestions

- **File**: `.cortex/synapse/prompts/review.md` (Improvement Suggestions section)
- Change from: "Specific, actionable recommendation and, where helpful, a brief before/after code example"
- Change to: "Each suggestion MUST include: (1) exact file:line, (2) concrete before/after code, (3) single-commit scope (max 3 files). Suggestions without file:line are INVALID."
- Add anti-pattern examples: BAD: "Narrow exception handlers across codebase" / GOOD: "In `src/cortex/validation/validation_config.py:92`, change `except Exception` to `except (OSError, json.JSONDecodeError, ValidationError)`"

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| "MUST include" for suggestions | review.md | Improvement suggestions section |
| Anti-pattern examples | review.md | review.md |

### Step 4: Add score-delta tracking

- **File**: `.cortex/synapse/prompts/review.md` (Report Format — scores section)
- Require loading previous review scores and showing delta: `Architecture: 8 (+0)` or `Error Handling: 7 (+1)`
- If a metric hasn't changed in 3+ consecutive reviews, flag it as "stale — requires targeted action plan"

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| Score delta format | review.md | Scores section |
| "stale" metric detection | review.md | review.md |

### Step 5: Add regression detection

- **File**: `.cortex/synapse/prompts/review.md` (new section after Step 3)
- "Step 4: Regression Check" — load previous review, compare: (a) any RESOLVED issue that reappeared? Flag as regression. (b) Any metric that dropped? Require explanation.
- Regressions are auto-promoted to High severity findings

#### Verification Checklist

| What to search for | Search scope | Files to re-read |
|---|---|---|
| "Regression Check" step | review.md | review.md |
| Auto-promotion to High severity | review.md | review.md |

## Dependencies

None.

## Success Criteria

- Reviews carry forward open issues from previous review
- Telemetry-only diffs expand scope to real code
- All improvement suggestions have exact file:line and before/after code
- Score deltas are visible across consecutive reviews
- After 3 reviews with this new prompt, at least 2 issues should be marked RESOLVED

## Testing Strategy

- Manual validation: run `/user-cortex/review` twice consecutively, verify second review references first review's findings
- Verify issue IDs are stable across reviews
- 95%+ test coverage maintained (prompt changes only, no source code)
