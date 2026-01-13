# Phase 9.0: Module Organization and Directory Structure

**Status:** 🔴 CRITICAL PRE-REQUISITE (Must complete before Phase 9.1)
**Goal:** Organize flat src/cortex/ structure into logical subdirectories
**Current State:** 56 files in root directory (too flat, poor discoverability)
**Target State:** Well-organized module hierarchy with clear boundaries
**Estimated Effort:** 8-12 hours
**Priority:** P0 (Blocker - must complete before file splitting in Phase 9.1)

---

## Problem Statement

The current `src/cortex/` structure is **too flat** with 56 Python files in the root directory:

```text
src/cortex/
├── __init__.py
├── adaptation_config.py
├── approval_manager.py
├── cache.py
├── consolidation_detector.py
├── container.py
├── context_detector.py
├── context_optimizer.py
├── dependency_graph.py
├── duplication_detector.py
├── exceptions.py
├── execution_validator.py
├── file_system.py
├── file_watcher.py
├── graph_algorithms.py
├── insight_engine.py
├── lazy_manager.py
├── learning_data_manager.py
├── learning_engine.py
├── link_parser.py
├── link_validator.py
├── logging_config.py
├── main.py
├── manager_groups.py
├── manager_utils.py
├── metadata_index.py
├── migration.py
├── optimization_config.py
├── optimization_strategies.py
├── pattern_analyzer.py
├── progressive_loader.py
├── protocols.py
├── quality_metrics.py
├── refactoring_engine.py
├── refactoring_executor.py
├── relevance_scorer.py
├── reorganization_planner.py
├── resources.py
├── responses.py
├── rollback_manager.py
├── rules_indexer.py
├── rules_manager.py
├── schema_validator.py
├── security.py
├── server.py
├── shared_rules_manager.py
├── split_analyzer.py
├── split_recommender.py
├── structure_analyzer.py
├── structure_manager.py
├── summarization_engine.py
├── template_manager.py
├── token_counter.py
├── transclusion_engine.py
├── validation_config.py
├── version_manager.py
├── guides/          (4 files)
├── managers/        (2 files)
├── templates/       (8 files)
└── tools/           (10 files)
```

**Issues:**

1. **Poor discoverability** - hard to find related modules
2. **No clear boundaries** - modules not grouped by function
3. **Difficult navigation** - 56 files to scan through
4. **Unclear dependencies** - relationships not obvious from structure

---

## Proposed Module Structure

Organize modules into **logical subdirectories by functional area** matching the phase structure:

```text
src/cortex/
├── __init__.py                  # Main package exports
├── main.py                      # Entry point
├── server.py                    # MCP server instance
│
├── core/                        # Phase 1: Core infrastructure
│   ├── __init__.py
│   ├── exceptions.py           # Custom exception hierarchy
│   ├── logging_config.py       # Logging infrastructure
│   ├── protocols.py            # Protocol definitions
│   ├── responses.py            # Standardized response helpers
│   ├── container.py            # Dependency injection container
│   ├── file_system.py          # File I/O operations
│   ├── file_watcher.py         # External change detection
│   ├── metadata_index.py       # Metadata tracking
│   ├── version_manager.py      # Version history
│   ├── migration.py            # Auto-migration
│   ├── token_counter.py        # Token counting
│   ├── dependency_graph.py     # Dependency tracking
│   ├── graph_algorithms.py     # Graph algorithms
│   ├── cache.py                # Caching infrastructure
│   └── security.py             # Security utilities
│
├── linking/                     # Phase 2: DRY Linking & Transclusion
│   ├── __init__.py
│   ├── link_parser.py          # Link parsing
│   ├── link_validator.py       # Link validation
│   └── transclusion_engine.py  # Transclusion resolution
│
├── validation/                  # Phase 3: Validation & Quality
│   ├── __init__.py
│   ├── schema_validator.py     # Schema validation
│   ├── duplication_detector.py # Duplication detection
│   ├── quality_metrics.py      # Quality scoring
│   └── validation_config.py    # Validation configuration
│
├── optimization/                # Phase 4: Token Optimization
│   ├── __init__.py
│   ├── context_optimizer.py    # Context optimization
│   ├── optimization_strategies.py  # Optimization strategies
│   ├── progressive_loader.py   # Progressive loading
│   ├── relevance_scorer.py     # Relevance scoring
│   ├── summarization_engine.py # Content summarization
│   ├── optimization_config.py  # Optimization configuration
│   ├── rules_manager.py        # Custom rules management
│   └── rules_indexer.py        # Rules indexing
│
├── analysis/                    # Phase 5.1: Pattern Analysis
│   ├── __init__.py
│   ├── pattern_analyzer.py     # Usage pattern tracking
│   ├── structure_analyzer.py   # Structure analysis
│   └── insight_engine.py       # Insight generation
│
├── refactoring/                 # Phase 5.2-5.4: Refactoring & Learning
│   ├── __init__.py
│   ├── refactoring_engine.py   # Refactoring suggestions
│   ├── refactoring_executor.py # Refactoring execution
│   ├── execution_validator.py  # Execution validation
│   ├── consolidation_detector.py  # Consolidation detection
│   ├── split_recommender.py    # Split recommendations
│   ├── split_analyzer.py       # Split analysis
│   ├── reorganization_planner.py  # Reorganization planning
│   ├── approval_manager.py     # User approval workflow
│   ├── rollback_manager.py     # Rollback management
│   ├── learning_engine.py      # Learning from feedback
│   ├── learning_data_manager.py   # Learning data persistence
│   └── adaptation_config.py    # Adaptation configuration
│
├── rules/                       # Phase 6: Shared Rules
│   ├── __init__.py
│   ├── shared_rules_manager.py # Git submodule integration
│   └── context_detector.py     # Context detection
│
├── structure/                   # Phase 8: Project Structure
│   ├── __init__.py
│   ├── structure_manager.py    # Structure lifecycle
│   └── template_manager.py     # Template management
│
├── managers/                    # Manager initialization (existing)
│   ├── __init__.py
│   ├── initialization.py       # Manager factory
│   ├── lazy_manager.py         # Lazy initialization wrapper
│   ├── manager_groups.py       # Manager grouping
│   └── manager_utils.py        # Manager utilities
│
├── tools/                       # MCP tools (existing)
│   ├── __init__.py
│   ├── consolidated.py         # Consolidated tools (to be split)
│   ├── phase1_foundation.py
│   ├── phase2_linking.py
│   ├── phase3_validation.py
│   ├── phase4_optimization.py
│   ├── phase5_analysis.py
│   ├── phase5_execution.py
│   ├── phase5_refactoring.py
│   ├── phase6_shared_rules.py
│   └── phase8_structure.py
│
├── templates/                   # Memory bank templates (existing)
│   ├── __init__.py
│   ├── memory_bank_instructions.py
│   ├── projectBrief.py
│   ├── product_context.py
│   ├── active_context.py
│   ├── system_patterns.py
│   ├── tech_context.py
│   └── progress.py
│
└── guides/                      # User guides (existing)
    ├── __init__.py
    ├── setup.py
    ├── usage.py
    ├── structure.py
    └── benefits.py
```

---

## Implementation Plan

### Step 1: Create Module Directories (1 hour)

Create 7 new subdirectories:

```bash
mkdir -p src/cortex/{core,linking,validation,optimization,analysis,refactoring,rules,structure}
```

Create `__init__.py` in each:

```bash
for dir in core linking validation optimization analysis refactoring rules structure; do
  touch src/cortex/$dir/__init__.py
done
```

### Step 2: Move Files to Subdirectories (2-3 hours)

#### Phase 1: Core (15 files)

```bash
mv src/cortex/{exceptions,logging_config,protocols,responses,container}.py src/cortex/core/
mv src/cortex/{file_system,file_watcher,metadata_index,version_manager,migration}.py src/cortex/core/
mv src/cortex/{token_counter,dependency_graph,graph_algorithms,cache,security}.py src/cortex/core/
```

#### Phase 2: Linking (3 files)

```bash
mv src/cortex/{link_parser,link_validator,transclusion_engine}.py src/cortex/linking/
```

#### Phase 3: Validation (4 files)

```bash
mv src/cortex/{schema_validator,duplication_detector,quality_metrics,validation_config}.py src/cortex/validation/
```

#### Phase 4: Optimization (8 files)

```bash
mv src/cortex/{context_optimizer,optimization_strategies,progressive_loader,relevance_scorer}.py src/cortex/optimization/
mv src/cortex/{summarization_engine,optimization_config,rules_manager,rules_indexer}.py src/cortex/optimization/
```

#### Phase 5.1: Analysis (3 files)

```bash
mv src/cortex/{pattern_analyzer,structure_analyzer,insight_engine}.py src/cortex/analysis/
```

#### Phase 5.2-5.4: Refactoring (13 files)

```bash
mv src/cortex/{refactoring_engine,refactoring_executor,execution_validator}.py src/cortex/refactoring/
mv src/cortex/{consolidation_detector,split_recommender,split_analyzer,reorganization_planner}.py src/cortex/refactoring/
mv src/cortex/{approval_manager,rollback_manager,learning_engine,learning_data_manager,adaptation_config}.py src/cortex/refactoring/
```

#### Phase 6: Rules (2 files)

```bash
mv src/cortex/{shared_rules_manager,context_detector}.py src/cortex/rules/
```

#### Phase 8: Structure (2 files)

```bash
mv src/cortex/{structure_manager,template_manager}.py src/cortex/structure/
```

#### Managers (move remaining 4 files)

```bash
mv src/cortex/{lazy_manager,manager_groups,manager_utils}.py src/cortex/managers/
```

### Step 3: Update All Imports (3-4 hours)

**Strategy:** Use automated search-replace for imports

**Example transformations:**

```python
# Before
from cortex.exceptions import MemoryBankError
from cortex.file_system import FileSystemManager
from cortex.link_parser import LinkParser

# After
from cortex.core.exceptions import MemoryBankError
from cortex.core.file_system import FileSystemManager
from cortex.linking.link_parser import LinkParser
```

**Files requiring updates:**

- All 56 Python files in src/cortex/
- All test files in tests/
- All tool files in tools/

**Automated approach:**

```bash
# Phase 1: Core imports
find src tests -name "*.py" -exec sed -i '' 's/from cortex\.exceptions/from cortex.core.exceptions/g' {} \;
find src tests -name "*.py" -exec sed -i '' 's/from cortex\.file_system/from cortex.core.file_system/g' {} \;
# ... (continue for all modules)

# Phase 2: Verify imports
.venv/bin/python -c "import cortex"
```

### Step 4: Update Package **init**.py (1 hour)

Update `src/cortex/__init__.py` with organized exports:

```python
"""Cortex - Structured documentation system for AI assistants."""

# Core infrastructure (Phase 1)
from cortex.core.exceptions import *
from cortex.core.protocols import *
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex

# Linking (Phase 2)
from cortex.linking.link_parser import LinkParser
from cortex.linking.transclusion_engine import TransclusionEngine

# Validation (Phase 3)
from cortex.validation.schema_validator import SchemaValidator
from cortex.validation.quality_metrics import QualityMetrics

# Optimization (Phase 4)
from cortex.optimization.context_optimizer import ContextOptimizer
from cortex.optimization.rules_manager import RulesManager

# Analysis (Phase 5.1)
from cortex.analysis.pattern_analyzer import PatternAnalyzer
from cortex.analysis.insight_engine import InsightEngine

# Refactoring (Phase 5.2-5.4)
from cortex.refactoring.refactoring_engine import RefactoringEngine
from cortex.refactoring.refactoring_executor import RefactoringExecutor

# Rules (Phase 6)
from cortex.rules.shared_rules_manager import SharedRulesManager

# Structure (Phase 8)
from cortex.structure.structure_manager import StructureManager

# Managers
from cortex.managers.initialization import get_managers

__version__ = "0.2.0"

__all__ = [
    # Core
    "FileSystemManager",
    "MetadataIndex",
    # Linking
    "LinkParser",
    "TransclusionEngine",
    # Validation
    "SchemaValidator",
    "QualityMetrics",
    # Optimization
    "ContextOptimizer",
    "RulesManager",
    # Analysis
    "PatternAnalyzer",
    "InsightEngine",
    # Refactoring
    "RefactoringEngine",
    "RefactoringExecutor",
    # Rules
    "SharedRulesManager",
    # Structure
    "StructureManager",
    # Managers
    "get_managers",
]
```

### Step 5: Run Tests and Fix Issues (2-3 hours)

```bash
# 1. Run full test suite
.venv/bin/pytest tests/ -v

# 2. Fix any import errors
# - Update test imports
# - Fix circular dependencies
# - Resolve any broken references

# 3. Verify server startup
.venv/bin/python -m cortex.main

# 4. Run type checker
.venv/bin/pyright src/ tests/

# 5. Run linter
.venv/bin/ruff check src/ tests/
```

---

## Benefits

### Improved Discoverability

✅ **Clear module boundaries** - easy to find related functionality
✅ **Logical grouping** - modules organized by phase/purpose
✅ **Reduced cognitive load** - scan 8 directories instead of 56 files

### Better Maintainability

✅ **Clear dependencies** - subdirectory structure shows relationships
✅ **Easier refactoring** - can work within single subdirectory
✅ **Better IDE support** - collapsible folders in file tree

### Enhanced Architecture

✅ **Enforces separation of concerns** - physical boundaries match logical boundaries
✅ **Prevents circular dependencies** - clearer import hierarchies
✅ **Supports future growth** - easy to add new modules to appropriate subdirectory

---

## Migration Strategy

### Option A: Big Bang (Recommended)

**Approach:** Move all files at once, update all imports, fix tests
**Effort:** 8-12 hours
**Risk:** Medium (but manageable with git)
**Benefit:** Clean cut, immediate improvement

### Option B: Incremental

**Approach:** Move one subdirectory at a time
**Effort:** 12-16 hours (more testing overhead)
**Risk:** Low
**Benefit:** Lower risk, easier rollback

**Recommendation:** Option A (Big Bang) - with proper git branching and comprehensive testing

---

## Testing Strategy

### Pre-Migration Verification

1. ✅ All 1,747 tests passing
2. ✅ Server starts successfully
3. ✅ No import warnings

### During Migration

1. Create git branch: `feature/module-organization`
2. Move files systematically (core → linking → validation → etc.)
3. Update imports as you go
4. Run tests after each module moved

### Post-Migration Validation

1. ✅ All 1,747 tests still passing (100% pass rate)
2. ✅ Server starts without errors
3. ✅ All tools registered correctly
4. ✅ Zero import errors
5. ✅ Pyright passes with 0 errors
6. ✅ Ruff passes with 0 warnings

---

## Impact on Phase 9.1

**Critical Pre-Requisite:** This must be completed **before** Phase 9.1 file splitting because:

1. **Clearer split boundaries** - organized structure makes it obvious where to split files
2. **Better file naming** - subdirectories provide context (e.g., `core/file_system.py` vs `file_system.py`)
3. **Easier testing** - can test subdirectories independently
4. **Reduced conflicts** - fewer files in root means less merge conflicts

**Updated Phase 9.1 Timeline:**

- Phase 9.0 (Module Organization): 8-12 hours (NEW)
- Phase 9.1 (Rules Compliance): 60-80 hours (unchanged)
- **Total:** 68-92 hours (was 60-80 hours)

---

## Success Criteria

### Phase 9.0 Completion Requirements

**Structure:**

- ✅ 8 new subdirectories created
- ✅ All 56 files moved to appropriate subdirectories
- ✅ Root directory contains only: **init**.py, main.py, server.py
- ✅ All **init**.py files created with proper exports

**Functionality:**

- ✅ All 1,747 tests passing (100% pass rate)
- ✅ Server starts successfully
- ✅ All 25 MCP tools working
- ✅ Zero import errors

**Quality:**

- ✅ Pyright: 0 errors, 0 warnings
- ✅ Ruff: 0 errors, 0 warnings
- ✅ All imports using new structure

**Documentation:**

- ✅ Updated CLAUDE.md with new structure
- ✅ Updated architecture.md with module organization
- ✅ Phase 9.0 completion summary created

---

## Risk Mitigation

### High Risk: Breaking Imports

**Risk:** Moving files breaks all imports
**Mitigation:**

- Use git branch for easy rollback
- Automated search-replace for imports
- Run tests continuously during migration
- Keep main.py imports simple

### Medium Risk: Circular Dependencies

**Risk:** New structure exposes circular imports
**Mitigation:**

- Review dependency graph before moving
- Use protocols to break cycles
- Move shared utilities to core first

### Low Risk: Test Failures

**Risk:** Tests fail after reorganization
**Mitigation:**

- Fix test imports immediately
- Run test suite after each module moved
- Maintain 100% pass rate throughout

---

## Implementation Checklist

- [ ] 1. Create 8 new subdirectories
- [ ] 2. Create **init**.py in each subdirectory
- [ ] 3. Move core/ files (15 files)
- [ ] 4. Move linking/ files (3 files)
- [ ] 5. Move validation/ files (4 files)
- [ ] 6. Move optimization/ files (8 files)
- [ ] 7. Move analysis/ files (3 files)
- [ ] 8. Move refactoring/ files (13 files)
- [ ] 9. Move rules/ files (2 files)
- [ ] 10. Move structure/ files (2 files)
- [ ] 11. Move remaining managers/ files (4 files)
- [ ] 12. Update all imports in src/
- [ ] 13. Update all imports in tests/
- [ ] 14. Update package **init**.py
- [ ] 15. Run full test suite
- [ ] 16. Fix any import errors
- [ ] 17. Verify server startup
- [ ] 18. Run Pyright (0 errors)
- [ ] 19. Run Ruff (0 warnings)
- [ ] 20. Update documentation
- [ ] 21. Create completion summary
- [ ] 22. Merge to main branch

---

## Next Steps

### Immediate Action

1. **Create git branch:** `git checkout -b feature/module-organization`
2. **Begin Phase 9.0:** Start with Step 1 (create directories)
3. **Follow checklist systematically**

### After Phase 9.0 Completion

- **Proceed to Phase 9.1:** File splitting will be much easier with organized structure
- **Update Phase 9 plans:** Adjust file paths in all Phase 9 documents

---

Last Updated: December 30, 2025
Status: 🔴 CRITICAL - Must complete before Phase 9.1
Priority: P0 (Pre-requisite for all Phase 9 work)
Estimated Duration: 8-12 hours
