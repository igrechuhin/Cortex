# Session Optimization: Rule Loading and Discovery (2026-02-18 Analysis)

## Source

Created from end-of-session analysis report: `.cortex/reviews/session-optimization-2026-02-18T11-13.md`

## Summary of Findings

- **Type violation**: `Any` used in `analyze_coverage_gaps.py`; fixed to `object` after user feedback.
- **Process gap**: Rules were not loaded before implementation; implement prompt Step 3 was skipped.
- **Prompt portability**: Project-specific doc path in implement/commit prompts; fixed to generic guidance.

## Root Causes

1. Implement prompt Step 3 (Read relevant rules) not executed before Step 4 (Implement).
2. When `rules()` returned empty, no fallback to get_synapse_rules or python-coding-standards.mdc.
3. Synapse prompts referenced repo-specific docs; should stay generic.

## Recommended Changes

### 1. Enforce rule loading in implement prompt (High)

- **Target**: `.cortex/synapse/prompts/implement-next-roadmap-step.md` Step 3
- **Change**: Add verification that rules were loaded before Step 4 (e.g. checklist: "Verify rules loaded: check for `Any` prohibition, Pydantic requirements, file size limits").
- **Impact**: Prevents type and standards violations.

### 2. Add rule loading reminder in Step 3.5 (Medium)

- **Target**: `.cortex/synapse/prompts/implement-next-roadmap-step.md` Step 3.5
- **Change**: Reminder: "If rules() returned empty, call get_synapse_rules(task_description='Python type annotations, coding standards') or read python-coding-standards.mdc to verify type annotation requirements."
- **Impact**: Ensures type standards are checked when rules indexing returns empty.

### 3. Document rule discovery fallback (Low)

- **Target**: AGENTS.md or implement prompt
- **Change**: Guidance: "When rules() returns empty, always check get_synapse_rules or python-coding-standards.mdc for type annotation rules (`Any` forbidden, `object` required)."
- **Impact**: Makes fallback explicit and discoverable.

## Implementation Steps

1. Edit implement prompt Step 3: add checklist item for verifying rules loaded (Any prohibition, Pydantic, file size).
2. Edit implement prompt Step 3.5: add fallback reminder for empty rules().
3. Edit AGENTS.md or implement prompt: add rule discovery fallback paragraph.
4. Run quality gate and update memory bank on completion.
