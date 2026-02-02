# Session Optimization (2026-02-02): Implement Prompt Memory Bank and Function Length

**Status**: PENDING  
**Created**: 2026-02-02  
**Source**: `.cortex/reviews/session-optimization-2026-02-02T14-28.md`  
**Priority**: High (Recommendation 1), Medium (Recommendation 2), Low (Recommendation 3)

## Goal

Implement the three recommendations from the session optimization analysis (Phase 46 implement session) so that: (1) all memory bank writes in implement sessions use `manage_file()` only; (2) agents are reminded to keep new functions under the 30-line limit during implementation; (3) session optimization analysis has a fallback when `rules()` is disabled.

## Context

The review at `.cortex/reviews/session-optimization-2026-02-02T14-28.md` identified:

- **Pattern 1**: Roadmap was updated via `StrReplace` on `.cortex/memory-bank/roadmap.md` instead of `manage_file(file_name="roadmap.md", operation="write", ...)`.
- **Pattern 2**: Function-length violations were introduced in `mcp_stability.py` and fixed only after the quality gate.

The review’s Implementation Plan is: (1) Update implement prompt Step 5 with requirement and prohibition for memory bank writes; (2) Add function-length reminder in Step 4 or 4.6; (3) Optional: add rules-disabled fallback in analyze-session-optimization.

## Implementation Steps

Steps define the implementation sequence; execute in order.

### Step 1: Enforce manage_file for all memory bank writes (implement prompt Step 5)

**Target**: `.cortex/synapse/prompts/implement-next-roadmap-step.md` (Step 5: Update Memory Bank)

**Tasks**:

1. Open Step 5 (Update Memory Bank) in the implement prompt.
2. Add an explicit **requirement**:
   - "All updates to roadmap.md, progress.md, activeContext.md, and any other memory bank file MUST be performed with `manage_file(file_name='...', operation='write', ...)`. Read current content with `manage_file(operation='read')` before writing."
3. Add an explicit **prohibition**:
   - "Do NOT use Write, StrReplace, or ApplyPatch on files under the memory bank directory (path from `get_structure_info()` → `structure_info.paths.memory_bank`). Using standard file tools for memory bank writes is a VIOLATION."
4. Place these as sub-bullets or a note immediately under the "Update the roadmap content" / "Use manage_file(... roadmap.md ...)" bullets so they are visible when executing Step 5.

**Acceptance**: Step 5 text includes the requirement and prohibition; no other behavior change required.

### Step 2: Add function-length reminder (implement prompt Step 4 or 4.6)

**Target**: `.cortex/synapse/prompts/implement-next-roadmap-step.md` (Step 4 Implement or Step 4.6 Verify Code Conformance)

**Tasks**:

1. In Step 4 (Implement) or Step 4.6 (Verify Code Conformance), add one sentence:
   - "When adding new functions, keep each under the project limit (≤30 logical lines); if a function grows beyond that, extract helpers before running the full quality gate."
2. Insert after the bullet that says "Ensure type annotations are complete" (Step 4) or in the "Verify structural compliance" list (Step 4.6).

**Acceptance**: The sentence appears in the implement prompt in the chosen location.

### Step 3 (Optional): Session-optimization rules fallback when rules() is disabled

**Target**: `.cortex/synapse/prompts/analyze-session-optimization.md` or the session-optimization-analyzer agent

**Tasks**:

1. Locate the "Read relevant rules" checklist item in the analyze-session-optimization prompt (or analyzer agent).
2. Add a fallback bullet:
   - "If rules indexing is disabled (`rules(operation='get_relevant', ...)` returns disabled), read key rules from the Synapse rules directory (path from `get_structure_info()` → `structure_info.paths.rules`) or from AGENTS.md/CLAUDE.md for coding standards and memory bank access."

**Acceptance**: The fallback instruction is present so session analysis can still load rules when indexing is off.

## Dependencies

- None. Synapse prompts and agents are in-repo; no code changes required beyond prompt/agent text.

## Success Criteria

1. Implement prompt Step 5 explicitly requires `manage_file()` for all memory bank writes and forbids Write/StrReplace/ApplyPatch on memory bank paths.
2. Implement prompt Step 4 or 4.6 includes a reminder to keep new functions ≤30 lines and extract helpers as needed.
3. (Optional) Analyze-session-optimization prompt or agent documents a fallback when `rules()` is disabled.

## Testing Strategy

- **No code under test**: Changes are prompt/agent text only.
- **Verification**: Integration test or manual check that the implement prompt file contains the new Step 5 requirement and prohibition and the Step 4/4.6 function-length sentence; optionally that the analyze-session-optimization prompt contains the rules fallback.
- **Regression**: Run existing implement-prompt and plan-creation integration tests (e.g. `test_implement_prompt_quality_gates.py`, `test_plan_creation_workflow_compliance.py`) to ensure no unintended prompt regressions.

## Risks and Mitigation

- **Prompt length**: Adding sentences may lengthen the implement prompt; keep additions minimal and scoped as above.
- **Clarity**: Wording is taken from the review; if feedback suggests ambiguity, tighten in a follow-up.

## Timeline

- Step 1: ~15 min.  
- Step 2: ~10 min.  
- Step 3: ~10 min (optional).  
- Total: under 1 hour.

## Notes

- This plan does not fix past sessions; it prevents recurrence by updating Synapse prompts and the session-optimization flow.
- Roadmap and memory bank updates for this plan MUST be done via `manage_file()` per the plan-creation and implement workflows.
