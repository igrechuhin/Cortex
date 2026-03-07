# Phase 91: HealthCheckReport Type Unification

**Status**: PENDING
**Priority**: Low
**Complexity**: Medium
**Category**: Refactoring

## Goal

Replace the loose `type HealthCheckReport = dict[str, object]` alias with `HealthCheckReportPayload` (Pydantic BaseModel) across all callers. Eliminate the dual representation.

## Context

- Chat session (implementation-10) discussed this explicitly. The user asked "Can use Pydantic v2 model instead of `object`?" and the agent suggested keeping the alias for backward compatibility.
- However, all internal callers already use `HealthCheckReportPayload.model_validate(report)`, meaning the loose dict type is a legacy surface.
- The user indicated preference for strict typing.
- `QualityImpact` enum was also promoted per user request during that session.

## Implementation Steps

### Step 1: Change the type alias

- In `health_check/models.py`, change `type HealthCheckReport = dict[str, object]` to `type HealthCheckReport = HealthCheckReportPayload`.

### Step 2: Update all producers

- CLI `__main__` and any other code that constructs a report dict must now construct a `HealthCheckReportPayload` instance.
- Search for all places that create or return `HealthCheckReport`.

### Step 3: Update all consumers

- Remove redundant `model_validate()` calls (data is already a model).
- Update type annotations in function signatures.

### Step 4: Verify

- Type checker passes.
- All tests pass.
- Health check pipeline works end-to-end.

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `dict[str, object]` in HealthCheckReport | `src/cortex/health_check/models.py` | Zero |
| `model_validate(report)` | Health check modules | Reduced (only at boundary) |

## Dependencies

- None.

## Success Criteria

- `HealthCheckReport` is a Pydantic BaseModel (not a dict alias).
- All callers construct and consume typed models.
- Zero type errors.

## Testing Strategy

- **Coverage Target**: 95%+ for health check modules.
- **Unit Tests**: Existing tests pass with model construction.
- **Integration Tests**: End-to-end health check produces valid typed reports.

## Timeline

- Estimated: 2–3 hours.
