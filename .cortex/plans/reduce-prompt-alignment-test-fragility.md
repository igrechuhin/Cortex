---
title: "Reduce Prompt-Alignment Test Fragility"
component: "tests/integration"
work_type: "refactor"
status: "PENDING"
priority: "Medium"
created: "2026-03-07"
execution_order: 20
depends_on: []
---

## Reduce Prompt-Alignment Test Fragility

**Status**: PENDING
**Priority**: Medium
**Complexity**: Medium
**Category**: Refactoring
**Component**: tests/integration
**Work Type**: refactor
**Execution Order**: 20

## Goal

Refactor `test_commit_workflow_prompt_alignment.py` from exact substring assertions to semantic/structural checks, preventing test breakage when prompts are reformatted or restructured.

## Context

- `tests/integration/test_commit_workflow_prompt_alignment.py` asserts specific substrings exist in Synapse prompts.
- Sessions 10 and 21 show 15-18 test failures from prompt changes, requiring the agent to add exact phrases back to prompts to satisfy tests.
- Key assertions include:
  - `test_parallel_block_is_nine_ten_eleven()` — checks steps 9, 10, 11 are parallel
  - `test_sequential_ranges_are_zero_eight_and_twelve_fourteen()` — checks sequential ranges
  - `test_steps_9_10_11_have_parallel_metadata()` — checks `can_run_in_parallel=True`
  - `test_prompt_contains_intermediate_validation_during_refactoring()` — Step 3.5 guidance
  - `test_commit_prompt_contains_duplicate_detection_before_creating_helpers()` — Step 3.6 guidance
- **CRITICAL**: This plan MUST complete BEFORE `simplify-commit-pipeline-structure` to avoid double refactoring.

## Implementation Steps

### Step 1: Identify all substring assertions

Read the full test file and list every `assert "..." in content` or `assertIn` call.

### Step 2: Categorize assertions

Group by what they're really testing:

- **Structural**: "Pipeline has 3 phases" → test for section headers
- **Behavioral**: "Parallel execution exists" → test for parallel metadata, not step numbers
- **Content**: "Intermediate validation mentioned" → test for concept, not exact wording

### Step 3: Rewrite tests as semantic checks

Replace:

```python
assert "Step 3.5" in content  # fragile
```

With:

```python
# Test that intermediate validation concept exists (any naming)
assert any(term in content.lower() for term in ["intermediate validation", "intermediate check", "mid-pipeline validation"])
```

For structural tests:

```python
# Test that pipeline has phases (not specific step numbers)
phase_pattern = re.compile(r"(?:Phase [A-C]|## .*(Quality|Documentation|Commit))")
assert phase_pattern.search(content), "Pipeline must define quality, documentation, and commit phases"
```

### Step 4: Run tests and verify

Ensure all refactored tests pass against the current (unchanged) prompts.

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `"Step 0.5"` or `"Step 1.5"` or `"Step 3.5"` | `test_commit_workflow_prompt_alignment.py` | Zero exact step-number assertions |
| `semantic` or `concept` or `pattern` | `test_commit_workflow_prompt_alignment.py` | Semantic checks present |

## Dependencies

- None. But MUST complete before `simplify-commit-pipeline-structure`.

## Success Criteria

- No exact substring assertions for step numbers or specific phrasings.
- Tests verify semantic requirements (phases exist, parallel execution configured, validation present).
- All tests pass against current prompts.

## Testing Strategy

- **Coverage Target**: 95% (these ARE the tests — they must pass)
- Run against current prompts: all pass
- Run after hypothetical prompt reformatting: still pass
