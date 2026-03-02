# Plan: Consolidate validate + check_structure_health

**Status**: PENDING
**Priority**: P3 (low)
**Estimated Effort**: 8–10 hours

## Goal

Evaluate and optionally implement consolidation of `validate` and `check_structure_health` into a single project health/validation tool. Different domains (Memory Bank vs filesystem structure) and different side-effect semantics (validate is read-only; check_structure_health has optional cleanup) make this a lower-priority consolidation.

## Context

- **validate**: schema, duplications, quality, infrastructure, timestamps, roadmap_sync — Memory Bank and config.
- **check_structure_health**: directory structure, stale files, optional cleanup (perform_cleanup, cleanup_actions).
- Overlap: `validate(check_type="infrastructure")` may relate to structure health. Consolidation would require careful handling of read-only vs write operations.

**Recommendation**: Proceed only if tool-count reduction is a high priority. Otherwise, keep separate.

**Reference**: [docs/guides/tool-description-altitude-rubric.md](../guides/tool-description-altitude-rubric.md) — target ≥ 4.

## Implementation Steps

**Implementation sequence**: Execute in order (Step 1 → 2 → … → 6). Step 1 is a go/no-go gate.

### Step 1: Go/no-go decision

- Document use cases for validate vs check_structure_health.
- Assess parameter overlap and whether a single tool can express both without confusing the model.
- **Decision**: If consolidation would harm clarity or require a large parameter union, close this plan as "not recommended."

### Step 2: Design consolidated API (if go)

- Tool name: `validate` (extended) or `project_health(operation=...)`.
- Operations: existing validate check_types plus `structure_health` (and optionally `structure_cleanup`).
- Parameters: validate params plus check_structure_health params (perform_cleanup, cleanup_actions, stale_days, dry_run), with operation-specific validation.

### Step 3: Implement dispatcher (if go)

- Route `check_type="structure_health"` (and `structure_cleanup`) to check_structure_health logic.
- Preserve read-only semantics for validate; preserve optional write for structure cleanup.
- Return format: match existing shapes per operation.

### Step 4: Update callers (if go)

- Update any callers of check_structure_health to use validate with new check_type.
- Update docs.

### Step 5: Deprecate check_structure_health (if go)

- Add shim or remove from registration.
- Update TOOL_CATEGORIES.

### Step 6: Verification (if go)

- Run full validation suite.
- Confirm tool count reduced by 1.

## Testing Strategy

- **Coverage target**: ≥ 95% for new/modified code.
- **Unit tests**: Test new check_type(s) produce correct behavior.
- **Regression**: Existing validate and check_structure_health tests must pass.
- **AAA pattern**: All tests follow Arrange-Act-Assert.

## Dependencies

- None.

## Success Criteria

- Either: (a) plan closed as "not recommended" with rationale, or (b) single tool provides both validate and structure health functionality, tool count reduced by 1.

## Risks & Mitigation

- **Risk**: Mixing read-only and write operations in one tool confuses the model. **Mitigation**: Use clear operation names; document side-effect semantics per operation.
- **Risk**: Different domains (Memory Bank vs filesystem) make tool description unwieldy. **Mitigation**: Step 1 go/no-go; prefer keeping separate if clarity suffers.
