# Phase 9.1: Critical Path Strategy

**Goal:** Achieve 9.8/10 rules compliance by fixing critical violations
**Scope:** Top 10 files + Top 15 functions (focused approach)
**Estimated Effort:** 10-15 hours
**Strategy:** Focus on highest-impact violations to reach compliance target

---

## Current State

### File Size Violations

**Total:** 33 files over 400 lines
**Critical Path:** Top 10 files (≥724 lines, total +4,238 lines over limit)

| # | File | Lines | Over Limit | Priority |
|---|------|-------|------------|----------|
| 1 | insight_engine.py | 1,051 | +651 | P0 |
| 2 | container.py | 948 | +548 | P0 |
| 3 | shared_rules_manager.py | 883 | +483 | P0 |
| 4 | refactoring_executor.py | 867 | +467 | P0 |
| 5 | template_manager.py | 858 | +458 | P0 |
| 6 | initialization.py | 785 | +385 | P0 |
| 7 | reorganization_planner.py | 778 | +378 | P0 |
| 8 | pattern_analyzer.py | 769 | +369 | P0 |
| 9 | structure_lifecycle.py | 765 | +365 | P0 |
| 10 | structure_analyzer.py | 724 | +324 | P0 |

### Function Length Violations

**Total:** 102 violations in 43 files
**Critical Path:** Top 15 functions (≥53 lines, +23 to +40 lines over)

| # | File | Function | Lines | Over Limit |
|---|------|----------|-------|------------|
| 1 | learning_engine.py | `adjust_suggestion_confidence` | 70 | +40 |
| 2 | structure_analyzer.py | `analyze_file_organization` | 69 | +39 |
| 3 | execution_validator.py | `validate_refactoring` | 69 | +39 |
| 4 | rollback_manager.py | `rollback_refactoring` | 68 | +38 |
| 5 | relevance_scorer.py | `extract_keywords` | 67 | +37 |
| 6 | phase4_optimization.py | `load_progressive_context` | 65 | +35 |
| 7 | rules_indexer.py | `index_rules` | 65 | +35 |
| 8 | reorganization_planner.py | `analyze_current_structure` | 64 | +34 |
| 9 | adaptation_config.py | `validate` | 63 | +33 |
| 10 | learning_engine.py | `_update_preferences` | 63 | +33 |
| 11 | optimization_strategies.py | `optimize_with_sections` | 62 | +32 |
| 12 | structure_analyzer.py | `find_dependency_chains` | 61 | +31 |
| 13 | shared_rules_manager.py | `update_shared_rule` | 60 | +30 |
| 14 | learning_engine.py | `get_learning_insights` | 60 | +30 |
| 15 | phase1_foundation.py | `get_version_history` | 59 | +29 |

---

## Implementation Plan

### Phase 1: Function Extraction (4-5 hours)

Extract top 15 function violations using systematic approach:

**Extraction Pattern:**

1. Identify helper function boundaries
2. Extract logical blocks (validation, processing, finalization)
3. Create descriptive helper function names
4. Maintain test coverage
5. Validate with pytest

**Example: `adjust_suggestion_confidence` (70 → <30 lines)**

```python
# Before (70 lines)
async def adjust_suggestion_confidence(self, feedback: dict[str, object]) -> None:
    """Adjust confidence based on feedback."""
    # Complex multi-step logic...

# After (25 lines + 3 helpers @~15 lines each)
async def adjust_suggestion_confidence(self, feedback: dict[str, object]) -> None:
    """Adjust confidence based on feedback."""
    metrics = self._calculate_confidence_metrics(feedback)
    adjustments = self._compute_confidence_adjustments(metrics)
    await self._apply_confidence_changes(adjustments)
```

**Files to Process:**

1. learning_engine.py (3 functions: #1, #10, #14)
2. structure_analyzer.py (2 functions: #2, #12)
3. execution_validator.py (1 function: #3)
4. rollback_manager.py (1 function: #4)
5. relevance_scorer.py (1 function: #5)
6. phase4_optimization.py (1 function: #6)
7. rules_indexer.py (1 function: #7)
8. reorganization_planner.py (1 function: #8)
9. adaptation_config.py (1 function: #9)
10. optimization_strategies.py (1 function: #11)
11. shared_rules_manager.py (1 function: #13)
12. phase1_foundation.py (1 function: #15)

### Phase 2: File Splitting (8-10 hours)

Split top 10 files using logical module boundaries:

#### 1. insight_engine.py (1,051 → 3 files) - 1.5h

```text
analysis/
├── insight_generator.py (~400 lines)
│   └── Core insight generation logic
├── insight_formatter.py (~350 lines)
│   └── Export formats (JSON, Markdown, Text)
└── insight_analyzer.py (~300 lines)
    └── Quality insights, pattern detection
```

**Split Strategy:**

- Move `generate_insights()` + helpers → insight_generator.py
- Move `export_*()` methods → insight_formatter.py
- Move `_generate_*_insights()` → insight_analyzer.py

#### 2. container.py (948 → 3 files) - 1.5h

```text
core/
├── service_container.py (~350 lines)
│   └── Core service registration and retrieval
├── container_lifecycle.py (~300 lines)
│   └── Initialization, shutdown, health checks
└── container_factory.py (~298 lines)
    └── Factory methods for creating services
```

#### 3. shared_rules_manager.py (883 → 2 files) - 1h

```text
rules/
├── rules_repository.py (~450 lines)
│   └── Git operations, rule loading, category management
└── rules_merger.py (~433 lines)
    └── Conflict resolution, rule merging
```

#### 4. refactoring_executor.py (867 → 2 files) - 1h

```text
refactoring/
├── refactoring_executor.py (~450 lines)
│   └── Execution workflow, validation, rollback
└── refactoring_operations.py (~417 lines)
    └── Consolidation, split, reorganization implementations
```

#### 5. template_manager.py (858 → 2 files) - 1h

```text
structure/
├── template_engine.py (~450 lines)
│   └── Template rendering, variable substitution
└── template_library.py (~408 lines)
    └── Template storage, retrieval, validation
```

#### 6. initialization.py (785 → 2 files) - 1h

```text
managers/
├── core_managers.py (~400 lines)
│   └── Core service initialization
└── optional_managers.py (~385 lines)
    └── Optional feature initialization
```

#### 7. reorganization_planner.py (778 → 2 files) - 1h

```text
refactoring/
├── reorganization_analyzer.py (~400 lines)
│   └── Structure analysis, category inference
└── reorganization_planner.py (~378 lines)
    └── Plan generation, optimization goals
```

#### 8. pattern_analyzer.py (769 → 2 files) - 1h

```text
analysis/
├── access_tracker.py (~400 lines)
│   └── Log recording, access pattern tracking
└── pattern_analyzer.py (~369 lines)
    └── Co-access analysis, temporal patterns
```

#### 9. structure_lifecycle.py (765 → 2 files) - 1h

```text
structure/
├── structure_lifecycle.py (~400 lines)
│   └── Setup, validation, housekeeping
└── structure_health.py (~365 lines)
    └── Health checks, diagnostics
```

#### 10. structure_analyzer.py (724 → 2 files) - 1h

```text
analysis/
├── structure_analyzer.py (~400 lines)
│   └── File organization, dependency analysis
└── complexity_analyzer.py (~324 lines)
    └── Complexity assessment, metrics
```

---

## Testing Strategy

### After Each Function Extraction

```bash
# Run tests for the modified module
pytest tests/unit/test_<module>.py -v

# Check coverage
pytest tests/unit/test_<module>.py --cov=src/cortex/<path>/<module>.py --cov-report=term-missing
```

### After Each File Split

```bash
# Run full test suite
gtimeout -k 5 300 python -m pytest -q

# Validate server startup
uv run cortex --version
```

### Final Validation

```bash
# Full test suite
gtimeout -k 5 600 ./.venv/bin/pytest

# File size check
find src/cortex -name "*.py" -exec wc -l {} \; | awk '$1 > 400'

# Function length check
python3 scripts/analyze_function_lengths.py
```

---

## Success Criteria

### File Size Compliance (Top 10)

- ✅ 0 files >400 lines in top 10
- ✅ All splits <400 lines each
- ✅ No duplicated code

### Function Length Compliance (Top 15)

- ✅ 15 functions extracted to <30 lines
- ✅ Helper functions properly named
- ✅ Test coverage maintained

### Test Quality

- ✅ All tests passing (100% pass rate)
- ✅ No regressions introduced
- ✅ Coverage maintained/improved

### Code Quality

- ✅ Imports updated correctly
- ✅ Type hints preserved
- ✅ Docstrings maintained
- ✅ No lint errors

---

## Risk Mitigation

### Breaking Changes

- **Risk:** File splits break imports
- **Mitigation:** Update all imports atomically, test after each split

### Test Failures

- **Risk:** Refactoring breaks functionality
- **Mitigation:** Run tests after every change, revert if tests fail

### Time Overrun

- **Risk:** 10-15h estimate insufficient
- **Mitigation:** Focus on P0 files first, defer remaining if needed

---

## Deliverables

1. ✅ Function extraction report (102 violations identified)
2. ✅ 15 functions extracted to <30 lines
3. ✅ 10 files split (20 new files created)
4. ✅ All tests passing
5. ✅ Phase 9.1 completion summary
6. ✅ Compliance report showing progress toward 9.8/10

---

## Next Steps

1. **Start with function extraction** (Phase 1)
   - Extract top 15 functions (4-5h)
   - Test after each extraction

2. **Proceed to file splitting** (Phase 2)
   - Split files in priority order (8-10h)
   - Test after each split

3. **Final validation** (Phase 3)
   - Run full test suite
   - Generate compliance report
   - Document remaining work for future phases

---

Last Updated: 2026-01-01
Status: Ready to implement
Estimated Duration: 12-15 hours
Priority: P0 (Critical path to 9.8/10)
