# Phase 9.2.3: Module Coupling - Fix Strategy

**Date:** 2026-01-03
**Status:** 🟡 PLANNED
**Target:** Architecture Score 9.0 → 9.8/10

---

## Problem Summary

The `core` layer has forward dependencies to higher-level layers through:

1. **container.py** - Imports concrete implementations from analysis, optimization, and refactoring layers
2. **container_factory.py** - Factory methods that create instances from all layers

This violates the layered architecture principle and creates 23 circular dependencies.

---

## Solution: TYPE_CHECKING Pattern

Use Python's `TYPE_CHECKING` pattern to separate runtime dependencies from type-checking dependencies.

### Strategy

1. **Runtime imports** - Only import from lower layers (core dependencies)
2. **Type-checking imports** - Import higher-layer types only for type hints (guarded by `if TYPE_CHECKING:`)
3. **Protocols** - Use protocol types instead of concrete types where possible
4. **Factory location** - Move factory logic to `managers` layer

---

## Implementation Plan

### Step 1: Refactor `container.py` (2-3 hours)

**Current Problem:**

```python
# Lines 12-57: Concrete imports from higher layers
from cortex.analysis.insight_engine import InsightEngine
from cortex.optimization.context_optimizer import ContextOptimizer
from cortex.refactoring.approval_manager import ApprovalManager
# ... many more
```

**Solution:**

```python
from typing import TYPE_CHECKING

# Runtime imports - only protocols and core types
from cortex.core.protocols import (
    ApprovalManagerProtocol,
    ContextOptimizerProtocol,
    # ... other protocols
)

# Type-checking imports - concrete types for IDE support
if TYPE_CHECKING:
    from cortex.analysis.insight_engine import InsightEngine
    from cortex.optimization.context_optimizer import ContextOptimizer
    from cortex.refactoring.approval_manager import ApprovalManager
    # ... all concrete types
```

**Changes Required:**

1. Add `if TYPE_CHECKING:` block
2. Move concrete imports into TYPE_CHECKING block
3. Update type hints to use protocols at runtime, concrete types in TYPE_CHECKING
4. Use forward references (strings) for types not available at runtime

**File Size:** ~350 lines → ~370 lines (within limit)

---

### Step 2: Move `container_factory.py` to `managers` layer (1-2 hours)

**Current Location:** `src/cortex/core/container_factory.py`
**New Location:** `src/cortex/managers/container_factory.py`

**Rationale:**

- Factory methods create instances from all layers
- Belongs in `managers` layer (L8) which coordinates all managers
- Removes forward dependencies from `core` layer

**Changes Required:**

1. Move file: `core/container_factory.py` → `managers/container_factory.py`
2. Update imports in dependent files:
   - `core/container.py`
   - `managers/initialization.py`
   - Any test files
3. Add to `managers/__init__.py` exports
4. Update documentation

**Impact:**

- Eliminates 5 layer boundary violations
- Eliminates 13+ circular dependencies
- Core layer becomes truly foundational

---

### Step 3: Update `container.py` to Use Moved Factory (30 min)

**Current:**

```python
from cortex.core.container_factory import (
    create_all_managers,
    # ...
)
```

**New:**

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cortex.managers.container_factory import (
        create_all_managers,
        # ...
    )
```

**Changes:**

1. Move factory import to TYPE_CHECKING block
2. Update `ManagerContainer.create()` method to accept factory as parameter
3. Document that factory must be provided from managers layer

---

### Step 4: Add Missing Protocols (1 hour)

Some managers used in container don't have protocols yet. Need to add:

1. **ConsolidationDetectorProtocol**
2. **SplitRecommenderProtocol**
3. **ReorganizationPlannerProtocol**
4. **LearningEngineProtocol**
5. **ProgressiveLoaderProtocol**
6. **SummarizationEngineProtocol**
7. **RulesManagerProtocol**

**Location:** `src/cortex/core/protocols.py`

**Template:**

```python
class ConsolidationDetectorProtocol(Protocol):
    """Protocol for consolidation detection."""

    async def detect_consolidation_opportunities(
        self,
        files: list[str],
        similarity_threshold: float = 0.80,
    ) -> list[dict[str, object]]:
        """Detect consolidation opportunities."""
        ...
```

---

### Step 5: Update Tests (1 hour)

**Files to Update:**

- `tests/unit/test_container.py`
- `tests/unit/test_container_factory.py` → Move to `tests/unit/managers/`
- `tests/integration/test_managers_initialization.py`

**Changes:**

1. Update import paths
2. Test that container works with protocol types
3. Test that factory creates correct instances
4. Verify no circular imports

---

## Verification Steps

### 1. Run Dependency Analysis

```bash
python3 scripts/analyze_dependencies.py
```

**Expected Output:**

```
=== Circular Dependencies ===
✅ No circular dependencies found!

=== Layer Violation Analysis ===
Found 1 layer violation(s):
  ⚠️  tools (level 9) → server (level 10)
```

### 2. Run Test Suite

```bash
pytest tests/ -v
```

**Expected:** All tests passing (1,537+ tests)

### 3. Check Type Hints

```bash
mypy src/cortex/core/container.py
```

**Expected:** No type errors

### 4. Verify Imports

```bash
python3 -c "from cortex.core.container import ManagerContainer; print('✅ No runtime circular imports')"
```

**Expected:** Module imports without errors

---

## Detailed Refactoring: container.py

### Before (Lines 12-57)

```python
from cortex.analysis.insight_engine import InsightEngine
from cortex.analysis.pattern_analyzer import PatternAnalyzer
from cortex.analysis.structure_analyzer import StructureAnalyzer
from cortex.core.container_factory import (
    AnalysisManagers,
    ExecutionManagers,
    FoundationManagers,
    LinkingManagers,
    OptimizationManagers,
    RefactoringManagers,
    create_all_managers,
)
# ... 30+ more concrete imports
```

### After

```python
from typing import TYPE_CHECKING

from cortex.core.protocols import (
    ApprovalManagerProtocol,
    ConsolidationDetectorProtocol,
    ContextOptimizerProtocol,
    DependencyGraphProtocol,
    FileSystemProtocol,
    InsightEngineProtocol,
    LearningEngineProtocol,
    LinkParserProtocol,
    LinkValidatorProtocol,
    MetadataIndexProtocol,
    PatternAnalyzerProtocol,
    ProgressiveLoaderProtocol,
    RefactoringEngineProtocol,
    RefactoringExecutorProtocol,
    RelevanceScorerProtocol,
    ReorganizationPlannerProtocol,
    RollbackManagerProtocol,
    RulesManagerProtocol,
    SplitRecommenderProtocol,
    StructureAnalyzerProtocol,
    SummarizationEngineProtocol,
    TokenCounterProtocol,
    TransclusionEngineProtocol,
    VersionManagerProtocol,
)

# Only import core layer dependencies at runtime
from cortex.core.file_watcher import FileWatcherManager
from cortex.core.migration import MigrationManager

# Type-checking only imports - not loaded at runtime
if TYPE_CHECKING:
    from cortex.analysis.insight_engine import InsightEngine
    from cortex.analysis.pattern_analyzer import PatternAnalyzer
    from cortex.analysis.structure_analyzer import StructureAnalyzer
    # ... all other concrete types for IDE support
```

---

## Estimated Impact

### Metrics Improvement

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Circular Dependencies | 23 | 0-2 | -91% to -100% |
| Layer Violations | 7 | 0-1 | -86% to -100% |
| Core Forward Deps | 5 | 0 | -100% |
| Architecture Score | 9.0/10 | 9.8/10 | +0.8 |

### Benefits

1. **✅ Eliminates circular dependencies**
   - Core layer no longer depends on higher layers at runtime
   - Clear dependency flow: managers → high layers → core

2. **✅ Enables modular testing**
   - Core layer can be tested in isolation
   - Mock implementations via protocols

3. **✅ Improves build times**
   - Fewer import cycles = faster imports
   - Lazy loading more effective

4. **✅ Better IDE support**
   - TYPE_CHECKING provides full type hints
   - No loss of autocomplete or type checking

5. **✅ Clearer architecture**
   - Obvious layer boundaries
   - Dependency flow matches intended design

---

## Risk Assessment

### Low Risk

- **TYPE_CHECKING pattern** - Standard Python pattern, well-tested
- **Protocol usage** - Already using protocols extensively
- **Test coverage** - Comprehensive test suite catches issues

### Mitigation

- Incremental changes with testing after each step
- Keep old code in git history for rollback
- Run full test suite after each change
- Profile to ensure no performance regression

---

## Timeline

| Task | Time | Status |
|------|------|--------|
| Add missing protocols | 1h | 🟡 Pending |
| Refactor container.py | 2-3h | 🟡 Pending |
| Move container_factory.py | 1-2h | 🟡 Pending |
| Update imports | 30min | 🟡 Pending |
| Update tests | 1h | 🟡 Pending |
| Verify & document | 30min | 🟡 Pending |
| **Total** | **6-8h** | **🟡 Planned** |

---

## Success Criteria

✅ **Must Have:**

1. Zero circular dependencies in core layer
2. Zero layer boundary violations (except tools→server)
3. All tests passing (1,537+)
4. No mypy type errors
5. Architecture score reaches 9.8/10

✅ **Should Have:**

1. Documentation updated
2. Architecture diagram created
3. Dependency rules documented
4. CI/CD checks added

✅ **Nice to Have:**

1. Performance benchmarks
2. Migration guide for other projects
3. Blog post about the refactoring

---

## Follow-up Tasks

### Phase 9.2.4: Optimize Optimization/Rules Coupling

After fixing core layer:

1. Move rules layer to L2 or L3
2. Refactor optimization → rules dependency
3. Use protocols for rules interfaces

**Estimated:** 2-3 hours
**Impact:** Eliminates 3 more circular dependencies

### Phase 9.3: Architecture Documentation

After all coupling fixes:

1. Create docs/architecture/layering.md
2. Create docs/architecture/dependency-rules.md
3. Update architecture diagrams
4. Add automated architecture tests

**Estimated:** 2-3 hours
**Impact:** Prevents future architectural degradation

---

## Conclusion

This fix strategy addresses the root cause of 23 circular dependencies by:

1. Using TYPE_CHECKING to separate runtime from type-checking imports
2. Moving factory logic to the appropriate layer (managers)
3. Adding missing protocols for complete abstraction
4. Establishing clear layer boundaries

**Expected Outcome:** Architecture score 9.0 → 9.8/10 with zero core layer circular dependencies.

---

**Prepared by:** Claude Code Agent
**Plan Date:** 2026-01-03
**Repository:** /Users/i.grechukhin/Repo/Cortex
**Next:** Implement Step 1 - Add missing protocols
