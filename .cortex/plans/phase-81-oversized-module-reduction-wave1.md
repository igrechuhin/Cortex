# Phase 81: Oversized Module Reduction — Wave 1 (Top 10)

**Status**: PENDING
**Priority**: Medium
**Complexity**: High
**Category**: Refactoring

## Goal

Reduce the top 10 largest Python modules in `src/` to comply with the 400-line limit, or document explicit exemptions with target split milestones.

## Context

- Project rules enforce max 400 lines per file, but **39 files** currently exceed this limit.
- The top 10 range from 560–732 LOC.
- Project review (2026-03-05) classified this as **Medium severity** — "either the rule is not enforced on core modules, or enforcement has broad exceptions."
- Quality gate currently passes because these files exist as legacy tech debt.

## Top 10 Files to Split

| LOC | File | Package |
|-----|------|---------|
| 732 | `core/security.py` | core |
| 700 | `validation/models.py` | validation |
| 683 | `core/dependency_graph.py` | core |
| 657 | `optimization/relevance_scorer.py` | optimization |
| 656 | `managers/factory.py` | managers |
| 655 | `optimization/config.py` | optimization |
| 653 | `optimization/rules_manager.py` | optimization |
| 624 | `managers/usage_tracker.py` | managers |
| 614 | `managers/container_factory.py` | managers |
| 607 | `refactoring/execution_validator.py` | refactoring |

## Approach

For each file:

1. Analyze logical groupings and extract cohesive sub-modules.
2. Create new files in the same package with focused responsibilities.
3. Re-export from `__init__.py` to preserve public API.
4. Update all import sites.
5. Ensure each resulting file is under 400 lines.

## Implementation Steps

### Step 1: `core/security.py` (732 → split)

- Extract input validation, path security, and git security into separate modules.
- ✅ Completed 2026-03-06: split `cortex.core.security` into `input_validation.py`, `html_security.py`, and `git_security.py` with a slim `security.py` aggregator re-exporting helpers; format, type_check, quality, and full tests passed (4913 tests, 92.42% coverage).

### Step 2: `validation/models.py` (700 → split)

- Group models by validation domain (timestamp, roadmap, schema, infrastructure).
- ✅ Completed 2026-03-06: split `cortex.validation.models` into `schema_models.py`, `quality_models.py`, `roadmap_models.py`, `infrastructure_models.py`, `timestamp_models.py` with slim `models.py` re-exports; fixed pre_commit_tools function-length violations; quality gate and tests passed (4938 tests, ~91.95% coverage).

### Step 3: `core/dependency_graph.py` (683 → split)

- Separate graph construction from graph analysis/traversal.

### Step 4: `optimization/relevance_scorer.py` (657 → split)

- Extract scoring strategies from the scorer orchestrator.

### Step 5: `managers/factory.py` (656 → split)

- Extract manager creation helpers into grouped factory modules.

### Step 6: `optimization/config.py` (655 → split)

- Separate config model definitions from config loading/validation.

### Step 7: `optimization/rules_manager.py` (653 → split)

- Extract rule loading, rule matching, and rule application into separate modules.

### Step 8: `managers/usage_tracker.py` (624 → split)

- Separate tracking data models from tracking logic.

### Step 9: `managers/container_factory.py` (614 → split)

- Extract container configuration from container assembly.

### Step 10: `refactoring/execution_validator.py` (607 → split)

- Separate validation rules from validation orchestration.

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| Files > 400 LOC in top 10 | `src/` | Zero matches for the 10 original files |
| Import errors | Full repo | Zero type errors |

## Dependencies

- None (each file split is independent).

## Success Criteria

- All 10 target files are under 400 lines (or have documented exemptions with a split plan).
- Zero type errors across `src/` and `tests/`.
- All tests pass with same or higher coverage.
- No public API changes (re-exports preserve compatibility).

## Testing Strategy

- **Coverage Target**: 95%+ maintained for all split modules.
- **Unit Tests**: Existing tests should pass without modification (re-exports).
- **Integration Tests**: Run full test suite after each split.
- **Regression Tests**: Verify import paths work for all consumers.

## Risks & Mitigation

- **Risk**: Circular imports after split. **Mitigation**: Analyze dependency graph before splitting.
- **Risk**: Breaking internal imports. **Mitigation**: Search all imports of each file before moving code.

## Timeline

- Estimated: 2–3 days (2–3 files per session).
