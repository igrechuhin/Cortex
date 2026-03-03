# Plan: Consolidate suggest_refactoring + apply_refactoring

**Status**: COMPLETE
**Priority**: P3 (low)
**Estimated Effort**: 8–12 hours

## Goal

Evaluate and optionally implement consolidation of `suggest_refactoring` and `apply_refactoring` into a single refactoring tool with operations for suggest, approve, apply, and rollback. Different intents (read vs write) and disjoint parameter sets make this a lower-priority consolidation.

## Context

- **suggest_refactoring**: Read-only; generates refactoring suggestions (type, min_similarity, size_threshold).
- **apply_refactoring**: approve, apply, rollback — state-changing (suggestion_id, execution_id, approval_id, etc.).
- Classic suggest-then-apply pattern. Merging would create a tool with disjoint operations and a large parameter union.

**Recommendation**: Keep separate unless tool-count reduction is critical. Suggest = discovery; apply = execution. Different intents and parameter sets.

**Reference**: [docs/guides/tool-description-altitude-rubric.md](../guides/tool-description-altitude-rubric.md) — target ≥ 4.

## Implementation Steps

**Implementation sequence**: Execute in order (Step 1 → 2 → … → 6). Step 1 is a go/no-go gate.

### Step 1: Go/no-go decision

- Document use cases: when does the agent call suggest vs apply?
- Assess whether a single `refactoring(operation="suggest"|"approve"|"apply"|"rollback", ...)` would improve or harm model tool selection.
- **Decision**: If consolidation would blur intent (suggest vs execute) or produce an unwieldy parameter schema, close this plan as "not recommended."
- **Outcome (2026-03-02)**: No-go. `suggest_refactoring` remains the read-only suggestion tool and `apply_refactoring` remains the state-changing approve/apply/rollback tool. A consolidated `refactoring(operation=...)` dispatcher would blur read vs write intent, require a large disjoint parameter union, and provide little benefit beyond the existing two-tool chain described in `docs/guides/advanced-tool-use.md`, so this consolidation is **not recommended**.

### Step 2: Design consolidated API (if go)

- Tool name: `refactoring(operation=...)`.
- Operations: `suggest`, `approve`, `apply`, `rollback`.
- Parameters: union with operation-specific validation (suggest: type, min_similarity, size_threshold; approve/apply: suggestion_id; rollback: execution_id).
- Document clearly which operations are read-only vs state-changing.

### Step 3: Implement dispatcher (if go)

- Route by operation to existing suggest_refactoring and apply_refactoring logic.
- Preserve exact behavior; no semantic changes.

### Step 4: Update callers (if go)

- Update refactoring-related prompts and agents.
- Replace suggest_refactoring with refactoring(operation="suggest").
- Replace apply_refactoring with refactoring(operation="approve"|"apply"|"rollback").

### Step 5: Deprecate old tools (if go)

- Remove suggest_refactoring and apply_refactoring from registration.
- Update TOOL_CATEGORIES.

### Step 6: Verification (if go)

- Run refactoring workflow tests.
- Confirm tool count reduced by 1.

## Testing Strategy

- **Coverage target**: ≥ 95% for new/modified code.
- **Unit tests**: Test each operation (suggest, approve, apply, rollback) produces correct behavior.
- **Integration tests**: Test full suggest → approve → apply → rollback lifecycle.
- **Regression**: Existing suggest_refactoring and apply_refactoring tests must pass (or be migrated).
- **AAA pattern**: All tests follow Arrange-Act-Assert.

## Dependencies

- None.

## Success Criteria

- Either: (a) plan closed as "not recommended" with rationale, or (b) single refactoring tool provides all functionality, tool count reduced by 1.

## Risks & Mitigation

- **Risk**: Merging read (suggest) and write (approve/apply/rollback) blurs tool purpose. **Mitigation**: Step 1 go/no-go; prefer keeping separate if model tool selection could worsen.
- **Risk**: Large parameter union confuses the model. **Mitigation**: Document operation-specific params clearly; use validation to reject invalid combinations.
