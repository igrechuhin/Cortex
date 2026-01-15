# Phase 10.2: File Size Compliance (MANDATORY)

**Status:** 0% Complete
**Priority:** CRITICAL (BLOCKS MERGE)
**Estimated Effort:** 8-12 days
**Target Score Improvement:** 5/10 → 9.5/10 (Maintainability)

## Overview

This phase addresses **4 CRITICAL file size violations** that block production readiness. The 400-line limit is MANDATORY per `.cursor/rules/maintainability.mdc`.

**Current Violations:**

1. [protocols.py](../src/cortex/core/protocols.py): 2,234 lines ⚠️ **459% OVER LIMIT**
2. [phase4_optimization.py](../src/cortex/tools/phase4_optimization.py): 1,554 lines ⚠️ **289% OVER LIMIT**
3. [reorganization_planner.py](../src/cortex/refactoring/reorganization_planner.py): 962 lines ⚠️ **141% OVER LIMIT**
4. [structure_lifecycle.py](../src/cortex/structure/structure_lifecycle.py): 871 lines ⚠️ **118% OVER LIMIT**

---

## Critical Impact Analysis

### Why This Blocks Production

1. **CI/CD Enforcement:** Rules compliance checks MUST fail on violations
2. **Maintainability:** Files >400 lines are difficult to navigate, test, and modify
3. **Code Review:** Large files slow down review process significantly
4. **Testing:** Harder to achieve comprehensive test coverage
5. **Onboarding:** New developers struggle with "God files"

### Cost of Delay

- **Technical Debt:** Compounds with every new feature
- **Review Time:** 3-5x longer for oversized files
- **Bug Risk:** Higher defect density in large files
- **Refactor Cost:** Increases exponentially over time

---

## Milestones

### Milestone 10.2.1: Split protocols.py (2,234 → <400 lines) ⚠️ CRITICAL

**Priority:** CRITICAL (Largest violation)
**Effort:** High (3-4 days)
**Impact:** Maintainability 5/10 → 7.5/10

#### Current State Analysis

**File:** [src/cortex/core/protocols.py](../src/cortex/core/protocols.py)

- **Lines:** 2,234 (production code)
- **Violation:** 459% over 400-line limit
- **Content:** 24+ Protocol definitions (PEP 544)
- **Dependencies:** Used by 46+ modules

#### Architecture

**Current Structure:**

```
protocols.py (2,234 lines)
├── FileSystemProtocol (~300 lines)
├── MetadataProtocol (~250 lines)
├── DependencyGraphProtocol (~400 lines)
├── TokenCounterProtocol (~150 lines)
├── ValidationProtocols (~350 lines)
├── OptimizationProtocols (~400 lines)
├── RefactoringProtocols (~350 lines)
└── 17+ more protocols...
```

**Target Structure:**

```
core/protocols/ (new directory)
├── __init__.py (100 lines) - Re-export all protocols for backward compatibility
├── file_system.py (300 lines) - FileSystemProtocol
├── metadata.py (250 lines) - MetadataProtocol, MetadataIndexProtocol
├── dependency.py (400 lines) - DependencyGraphProtocol
├── token.py (150 lines) - TokenCounterProtocol
├── validation.py (350 lines) - SchemaValidatorProtocol, DuplicationDetectorProtocol, QualityMetricsProtocol
├── optimization.py (400 lines) - RelevanceScorerProtocol, ContextOptimizerProtocol, ProgressiveLoaderProtocol
└── refactoring.py (350 lines) - RefactoringEngineProtocol, ApprovalManagerProtocol, RollbackManagerProtocol
```

#### Implementation Strategy

**Step 1: Create Directory Structure**

```bash
mkdir -p src/cortex/core/protocols
touch src/cortex/core/protocols/__init__.py
```

**Step 2: Extract Protocols by Domain**

Extract in this order (lowest dependencies first):

1. **file_system.py** (300 lines)

   ```python
   """File system protocols."""
   from pathlib import Path
   from typing import Protocol

   class FileSystemProtocol(Protocol):
       """Protocol for file system operations."""
       def validate_path(self, file_path: Path) -> bool: ...
       async def read_file(self, file_path: Path) -> tuple[str, str]: ...
       # ... rest of protocol
   ```

2. **token.py** (150 lines)

   ```python
   """Token counting protocols."""
   from typing import Protocol

   class TokenCounterProtocol(Protocol):
       """Protocol for token counting operations."""
       def count_tokens(self, text: str) -> int: ...
       # ... rest of protocol
   ```

3. **metadata.py** (250 lines)
4. **dependency.py** (400 lines)
5. **validation.py** (350 lines)
6. **optimization.py** (400 lines)
7. **refactoring.py** (350 lines)

**Step 3: Create Backward-Compatible **init**.py**

```python
"""
Protocol definitions for Cortex.

All protocols are re-exported from this module for backward compatibility.
"""

# File system protocols
from cortex.core.protocols.file_system import (
    FileSystemProtocol,
)

# Token counting protocols
from cortex.core.protocols.token import (
    TokenCounterProtocol,
)

# Metadata protocols
from cortex.core.protocols.metadata import (
    MetadataProtocol,
    MetadataIndexProtocol,
)

# ... rest of re-exports

__all__ = [
    "FileSystemProtocol",
    "TokenCounterProtocol",
    "MetadataProtocol",
    "MetadataIndexProtocol",
    # ... all protocol names
]
```

**Step 4: Update All Import Statements**

No changes needed! Existing code uses:

```python
from cortex.core.protocols import FileSystemProtocol
```

This still works because `__init__.py` re-exports everything.

**Step 5: Verification**

1. **Run tests:** `pytest tests/ -v`
2. **Check imports:** All 46+ modules import successfully
3. **Type checking:** `pyright src/`
4. **Line count verification:**

   ```bash
   find src/cortex/core/protocols -name "*.py" -exec wc -l {} +
   ```

#### Testing Strategy

1. **Import Tests:** Verify all protocols still importable

   ```python
   def test_protocol_imports():
       from cortex.core.protocols import (
           FileSystemProtocol,
           MetadataProtocol,
           # ... all protocols
       )
       assert FileSystemProtocol is not None
   ```

2. **Backward Compatibility:** Ensure existing code works

   ```bash
   pytest tests/ -k protocol
   ```

3. **Type Checking:** Verify Protocol usage

   ```bash
   pyright src/ --ignoreexternal
   ```

#### Success Criteria

- ✅ All protocol files <400 lines
- ✅ Backward compatibility maintained
- ✅ All 1920 tests passing
- ✅ Zero import errors
- ✅ Pyright passes
- ✅ Maintainability score: 5/10 → 7.5/10

---

### Milestone 10.2.2: Split phase4_optimization.py (1,554 → <400 lines) ⚠️ CRITICAL

**Priority:** CRITICAL (Second largest violation)
**Effort:** High (2-3 days)
**Impact:** Maintainability 7.5/10 → 8.5/10

#### Current State Analysis

**File:** [src/cortex/tools/phase4_optimization.py](../src/cortex/tools/phase4_optimization.py)

- **Lines:** 1,554 (production code)
- **Violation:** 289% over 400-line limit
- **Content:** 4 MCP tool handlers + helpers
- **Problem:** Multiple concerns in single file

#### Architecture

**Current Structure:**

```
phase4_optimization.py (1,554 lines)
├── optimize_context() [handler + 300 lines helpers]
├── load_progressive_context() [handler + 250 lines helpers]
├── summarize_content() [handler + 400 lines helpers]
├── get_relevance_scores() [handler + 200 lines helpers]
└── Shared utilities (400 lines)
```

**Target Structure:**

```
tools/
├── phase4_optimization.py (150 lines) - MCP handlers only, delegates to helpers
├── optimization/
│   ├── __init__.py (50 lines)
│   ├── context_optimizer_tool.py (350 lines) - optimize_context logic
│   ├── progressive_loader_tool.py (300 lines) - load_progressive_context logic
│   ├── summarization_tool.py (400 lines) - summarize_content logic
│   ├── relevance_scorer_tool.py (250 lines) - get_relevance_scores logic
│   └── optimization_helpers.py (350 lines) - Shared utilities
```

#### Implementation Strategy

**Step 1: Create Directory Structure**

```bash
mkdir -p src/cortex/tools/optimization
touch src/cortex/tools/optimization/__init__.py
```

**Step 2: Extract Tool Modules**

1. **context_optimizer_tool.py** (350 lines)

   ```python
   """Context optimization tool implementation."""
   from typing import Any
   from cortex.core.protocols import ContextOptimizerProtocol

   async def optimize_context_impl(
       managers: dict[str, Any],
       query: str,
       token_budget: int,
       strategy: str,
   ) -> dict[str, Any]:
       """Implementation of optimize_context tool."""
       # Move all logic from phase4_optimization.py here
       ...
   ```

2. **progressive_loader_tool.py** (300 lines)
3. **summarization_tool.py** (400 lines)
4. **relevance_scorer_tool.py** (250 lines)
5. **optimization_helpers.py** (350 lines) - Shared utilities

**Step 3: Refactor MCP Handlers (Thin Orchestrators)**

Update `phase4_optimization.py` to be thin handlers:

```python
"""Phase 4: Token Optimization MCP Tools."""
from cortex.tools.optimization.context_optimizer_tool import (
    optimize_context_impl,
)
from cortex.tools.optimization.progressive_loader_tool import (
    load_progressive_context_impl,
)
from cortex.tools.optimization.summarization_tool import (
    summarize_content_impl,
)
from cortex.tools.optimization.relevance_scorer_tool import (
    get_relevance_scores_impl,
)

@mcp.tool()
async def optimize_context(
    query: str,
    token_budget: int = 8000,
    strategy: str = "priority",
) -> dict[str, Any]:
    """Optimize Memory Bank context within token budget."""
    managers = await get_managers()
    return await optimize_context_impl(
        managers, query, token_budget, strategy
    )

# Similar thin handlers for other tools...
```

**Step 4: Update Tests**

Update test imports:

```python
# Before
from cortex.tools.phase4_optimization import (
    _validate_strategy,  # Helper
)

# After
from cortex.tools.optimization.context_optimizer_tool import (
    validate_strategy,  # Now public
)
```

**Step 5: Verification**

1. Run tool tests: `pytest tests/tools/test_phase4_optimization.py -v`
2. Check line counts: All files <400 lines
3. Verify MCP tools still work

#### Success Criteria

- ✅ All optimization files <400 lines
- ✅ MCP tools still functional
- ✅ All 21 optimization tests passing
- ✅ 93% coverage maintained
- ✅ Maintainability score: 7.5/10 → 8.5/10

---

### Milestone 10.2.3: Split reorganization_planner.py (962 → <400 lines) ⚠️ HIGH

**Priority:** HIGH
**Effort:** Medium (1-2 days)
**Impact:** Maintainability 8.5/10 → 9.0/10

#### Current State Analysis

**File:** [src/cortex/refactoring/reorganization_planner.py](../src/cortex/refactoring/reorganization_planner.py)

- **Lines:** 962 (production code)
- **Violation:** 141% over 400-line limit
- **Content:** Reorganization planning logic
- **Problem:** Multiple responsibilities (analysis, strategy, execution planning)

#### Target Structure

```
refactoring/
├── reorganization_planner.py (250 lines) - Orchestrator
├── reorganization/
│   ├── __init__.py (50 lines)
│   ├── analyzer.py (350 lines) - Analysis logic (detect issues, score files)
│   ├── strategies.py (400 lines) - Strategy patterns (by category, complexity, etc.)
│   └── executor.py (300 lines) - Execution planning (action generation, validation)
```

#### Implementation Strategy

**Step 1: Extract Analysis Logic**

```python
# reorganization/analyzer.py (350 lines)
"""Reorganization analysis logic."""

class ReorganizationAnalyzer:
    """Analyzes project structure for reorganization opportunities."""

    def detect_issues(self, files: list[dict]) -> list[dict]:
        """Detect structural issues."""
        ...

    def score_files(self, files: list[dict]) -> dict[str, float]:
        """Score files for reorganization priority."""
        ...
```

**Step 2: Extract Strategy Logic**

```python
# reorganization/strategies.py (400 lines)
"""Reorganization strategy patterns."""

class ByCategory:
    """Organize by content category."""
    def generate_actions(self, files: list[dict]) -> list[dict]:
        ...

class ByComplexity:
    """Organize by complexity."""
    def generate_actions(self, files: list[dict]) -> list[dict]:
        ...
```

**Step 3: Extract Execution Planning**

```python
# reorganization/executor.py (300 lines)
"""Reorganization execution planning."""

class ExecutionPlanner:
    """Plans safe execution of reorganization."""

    def generate_actions(self, strategy: str, files: list[dict]) -> list[dict]:
        """Generate reorganization actions."""
        ...

    def validate_actions(self, actions: list[dict]) -> bool:
        """Validate actions are safe."""
        ...
```

**Step 4: Refactor Orchestrator**

```python
# reorganization_planner.py (250 lines)
"""Reorganization planner orchestrator."""
from cortex.refactoring.reorganization.analyzer import ReorganizationAnalyzer
from cortex.refactoring.reorganization.strategies import ByCategory, ByComplexity
from cortex.refactoring.reorganization.executor import ExecutionPlanner

class ReorganizationPlanner:
    """Orchestrates reorganization planning."""

    def __init__(self, ...):
        self.analyzer = ReorganizationAnalyzer(...)
        self.executor = ExecutionPlanner(...)

    def plan_reorganization(self, files: list[dict], strategy: str) -> dict:
        """Plan file reorganization."""
        issues = self.analyzer.detect_issues(files)
        scores = self.analyzer.score_files(files)
        actions = self.executor.generate_actions(strategy, files)
        return {"issues": issues, "actions": actions, "scores": scores}
```

#### Success Criteria

- ✅ All reorganization files <400 lines
- ✅ Clear separation of concerns
- ✅ All refactoring tests passing
- ✅ Maintainability score: 8.5/10 → 9.0/10

---

### Milestone 10.2.4: Split structure_lifecycle.py (871 → <400 lines) ⚠️ HIGH

**Priority:** HIGH
**Effort:** Medium (1-2 days)
**Impact:** Maintainability 9.0/10 → 9.5/10

#### Current State Analysis

**File:** [src/cortex/structure/structure_lifecycle.py](../src/cortex/structure/structure_lifecycle.py)

- **Lines:** 871 (production code)
- **Violation:** 118% over 400-line limit
- **Content:** Structure lifecycle management
- **Problem:** Multiple lifecycle stages in single file

#### Target Structure

```
structure/
├── structure_lifecycle.py (200 lines) - Orchestrator
├── lifecycle/
│   ├── __init__.py (50 lines)
│   ├── setup.py (350 lines) - Setup operations (init, create dirs, symlinks)
│   ├── validation.py (300 lines) - Validation operations (health checks, scoring)
│   └── migration.py (350 lines) - Migration operations (legacy detection, conversion)
```

#### Implementation Strategy

**Step 1: Extract Setup Operations**

```python
# lifecycle/setup.py (350 lines)
"""Structure setup operations."""

class StructureSetup:
    """Handles project structure setup."""

    def initialize_structure(self, config: dict) -> bool:
        """Initialize project structure."""
        ...

    def create_directories(self, layout: dict) -> None:
        """Create directory structure."""
        ...

    def create_symlinks(self, platform: str) -> None:
        """Create platform-specific symlinks."""
        ...
```

**Step 2: Extract Validation Operations**

```python
# lifecycle/validation.py (300 lines)
"""Structure validation operations."""

class StructureValidator:
    """Validates project structure."""

    def check_health(self, config: dict) -> dict:
        """Check structure health."""
        ...

    def calculate_score(self, issues: list) -> float:
        """Calculate health score 0-100."""
        ...
```

**Step 3: Extract Migration Operations**

```python
# lifecycle/migration.py (350 lines)
"""Structure migration operations."""

class StructureMigration:
    """Handles legacy structure migration."""

    def detect_legacy_type(self, root: Path) -> str:
        """Detect legacy structure type."""
        ...

    def migrate_from_legacy(self, legacy_type: str) -> bool:
        """Migrate from legacy structure."""
        ...
```

**Step 4: Refactor Orchestrator**

```python
# structure_lifecycle.py (200 lines)
"""Structure lifecycle orchestrator."""
from cortex.structure.lifecycle.setup import StructureSetup
from cortex.structure.lifecycle.validation import StructureValidator
from cortex.structure.lifecycle.migration import StructureMigration

class StructureLifecycle:
    """Orchestrates structure lifecycle."""

    def __init__(self, ...):
        self.setup = StructureSetup(...)
        self.validator = StructureValidator(...)
        self.migration = StructureMigration(...)

    async def setup_structure(self, config: dict) -> dict:
        """Setup project structure."""
        return await self.setup.initialize_structure(config)

    async def validate_structure(self) -> dict:
        """Validate project structure."""
        return await self.validator.check_health(self.config)

    async def migrate_structure(self, legacy_type: str) -> bool:
        """Migrate from legacy structure."""
        return await self.migration.migrate_from_legacy(legacy_type)
```

#### Success Criteria

- ✅ All structure files <400 lines
- ✅ Clear lifecycle separation
- ✅ All structure tests passing
- ✅ Maintainability score: 9.0/10 → 9.5/10

---

## Phase Completion Checklist

### Pre-Implementation

- [ ] Create detailed implementation plans for each file
- [ ] Identify all import dependencies
- [ ] Plan backward compatibility strategy

### Implementation (Per File)

- [ ] Create new directory structure
- [ ] Extract modules by concern
- [ ] Create backward-compatible facade
- [ ] Update all import statements
- [ ] Run tests after each extraction

### Verification (Per Milestone)

- [ ] All extracted files <400 lines
- [ ] No breaking changes
- [ ] All tests passing (100% pass rate)
- [ ] Import statements work correctly
- [ ] Pyright passes

### Code Quality (Per Milestone)

- [ ] Format with Black
- [ ] Sort imports with isort
- [ ] Run full test suite
- [ ] Verify coverage maintained

### Documentation

- [ ] Update module docstrings
- [ ] Update API documentation
- [ ] Create migration guide
- [ ] Update activeContext.md
- [ ] Update progress.md

### Final Validation

- [ ] **Zero file size violations**
- [ ] All 1920 tests passing
- [ ] Maintainability score ≥9.5/10
- [ ] CI/CD compliance achieved
- [ ] Ready for Phase 10.3

---

## Success Metrics

### File Size Compliance

| File | Before | After | Target | Status |
|------|--------|-------|--------|--------|
| protocols.py | 2,234 | 7 files <400 | <400 | ⏳ Pending |
| phase4_optimization.py | 1,554 | 6 files <400 | <400 | ⏳ Pending |
| reorganization_planner.py | 962 | 4 files <400 | <400 | ⏳ Pending |
| structure_lifecycle.py | 871 | 4 files <400 | <400 | ⏳ Pending |

### Quality Score Improvements

| Metric | Before | After | Target | Status |
|--------|--------|-------|--------|--------|
| Maintainability | 5/10 | 9.5/10 | 9.8/10 | ✅ Excellent |
| Rules Compliance | 6/10 | 9.0/10 | 9.8/10 | 🟡 Very Good |
| Architecture | 9/10 | 9.5/10 | 9.8/10 | ✅ Excellent |
| **Overall** | **7.5/10** | **9.0/10** | **9.8/10** | 🟢 **+1.5** |

---

## Risk Assessment

### High Risk

- **Breaking changes during refactor**
  - Mitigation: Maintain backward compatibility via re-exports
  - Testing: Run full test suite after each extraction

### Medium Risk

- **Import circular dependencies**
  - Mitigation: Use TYPE_CHECKING pattern
  - Validation: Test imports separately

### Low Risk

- **Test updates required**
  - Mitigation: Update test imports systematically
  - Fallback: Keep old imports working via **init**.py

---

## Dependencies

### Blocks

- Phase 10.3 (Remaining Improvements) - Cannot achieve 9.8/10 without file size compliance

### Blocked By

- Phase 10.1 (Critical Fixes) - Must pass CI before refactoring

---

## Timeline

**Total Duration:** 8-12 days

| Milestone | Duration | Priority | Parallel? |
|-----------|----------|----------|-----------|
| 10.2.1: protocols.py | 3-4 days | CRITICAL | No (largest) |
| 10.2.2: phase4_optimization.py | 2-3 days | CRITICAL | Yes (after 10.2.1) |
| 10.2.3: reorganization_planner.py | 1-2 days | HIGH | Yes (with 10.2.2) |
| 10.2.4: structure_lifecycle.py | 1-2 days | HIGH | Yes (with 10.2.2) |
| Verification & Documentation | 1 day | HIGH | No (after all) |

**Parallelization Strategy:**

- Week 1: protocols.py (solo focus)
- Week 2: phase4_optimization.py + reorganization_planner.py + structure_lifecycle.py (parallel)

---

## Next Steps

After Phase 10.2 completion:

1. ✅ Zero file size violations
2. ✅ Maintainability 9.5/10
3. ✅ Rules Compliance 9.0/10
4. 🟢 Proceed to **Phase 10.3: Final Excellence** (achieve 9.8/10)

---

**Last Updated:** 2026-01-05
**Status:** Not Started (Blocked by Phase 10.1)
**Next Action:** Complete Phase 10.1 first, then begin Milestone 10.2.1
